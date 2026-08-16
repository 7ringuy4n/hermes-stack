#!/usr/bin/env bash
# Self-heal Zalo channel (bridge-focused).
# Intended as systemd timer (every ~1–2 min) when ENABLE_ZALO=1.
#
# Signals:
#   - bridge /health unreachable → restart user Zalo unit
#   - loggedIn but sseClients==0 → restart BRIDGE only (default)
#     Hermes is NOT restarted (restart storms when SSE is slow to reconnect).
#   - Optional: ZALO_WATCH_RESTART_HERMES=1 restores old hermes restart behavior
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a

PORT="${ZALO_PLUGIN_PORT:-8787}"
HEALTH_URL="${ZALO_WATCH_HEALTH_URL:-http://127.0.0.1:${PORT}/health}"
# Prefer explicit env; else lab /data/hermes; else assistant default
if [[ -n "${ASSISTANT_DATA_DIR:-}" ]]; then
  _data_root="$ASSISTANT_DATA_DIR"
elif [[ -n "${HERMES_DATA_DIR:-}" ]]; then
  _data_root="$HERMES_DATA_DIR"
elif [[ -d /data/hermes ]]; then
  _data_root="/data/hermes"
else
  _data_root="/data/assistant"
fi
STATE_DIR="${_data_root}/watch"
STATE_FILE="${STATE_DIR}/zalo-watch.state"
COOLDOWN_FILE="${STATE_DIR}/zalo-watch.cooldown"
# Higher defaults: Hermes needs minutes after boot before SSE attaches
SSE_MISS_LIMIT="${ZALO_WATCH_SSE_MISS:-15}"
SSE_COOLDOWN_S="${ZALO_WATCH_SSE_COOLDOWN:-1800}"
BRIDGE_COOLDOWN_S="${ZALO_WATCH_BRIDGE_COOLDOWN:-90}"
RESTART_HERMES="${ZALO_WATCH_RESTART_HERMES:-0}"
HERMES_CTR="${HERMES_CONTAINER:-hermes}"
PROXY_CTR="${ZALO_PROXY_CONTAINER:-zalo-proxy}"
if [[ "$(id -u)" -ne 0 ]]; then SUDO=sudo; else SUDO=; fi

if ! mkdir -p "$STATE_DIR" 2>/dev/null; then
  $SUDO mkdir -p "$STATE_DIR"
  $SUDO chown "$(id -u):$(id -g)" "$STATE_DIR" 2>/dev/null || true
fi
# Ensure state file is writable (lab /data/hermes is often root-owned)
if [[ ! -w "$STATE_DIR" ]]; then
  $SUDO mkdir -p "$STATE_DIR"
  $SUDO chown -R "$(id -u):$(id -g)" "$STATE_DIR" 2>/dev/null \
    || $SUDO chmod 777 "$STATE_DIR" 2>/dev/null \
    || true
fi
touch "$STATE_FILE" 2>/dev/null || {
  $SUDO touch "$STATE_FILE"
  $SUDO chown "$(id -u):$(id -g)" "$STATE_FILE" 2>/dev/null || true
}

log() { echo "$(date -Is) zalo-watch: $*"; }

read_state() {
  SSE_MISS=0
  LAST_ACTION=""
  # shellcheck disable=SC1090
  [[ -f "$STATE_FILE" ]] && source "$STATE_FILE" || true
  SSE_MISS="${SSE_MISS:-0}"
}

write_state() {
  local body
  body=$(cat <<EOF
SSE_MISS=${SSE_MISS:-0}
LAST_ACTION=$(printf '%q' "${LAST_ACTION:-}")
LAST_TS=$(date +%s)
EOF
)
  if [[ -w "$STATE_DIR" ]] || [[ -w "$STATE_FILE" ]]; then
    printf '%s\n' "$body" >"$STATE_FILE"
  else
    printf '%s\n' "$body" | $SUDO tee "$STATE_FILE" >/dev/null
    $SUDO chown "$(id -u):$(id -g)" "$STATE_FILE" 2>/dev/null || true
  fi
}

in_cooldown() {
  local sec="${1:-120}"
  [[ -f "$COOLDOWN_FILE" ]] || return 1
  local then now
  then="$(cat "$COOLDOWN_FILE" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  [[ $((now - then)) -lt "$sec" ]]
}

mark_cooldown() {
  if [[ -w "$STATE_DIR" ]]; then
    date +%s >"$COOLDOWN_FILE"
  else
    date +%s | $SUDO tee "$COOLDOWN_FILE" >/dev/null
    $SUDO chown "$(id -u):$(id -g)" "$COOLDOWN_FILE" 2>/dev/null || true
  fi
}

restart_bridge() {
  log "restart host Zalo bridge unit"
  systemctl --user try-restart com.hermes.zaloplugin.service 2>/dev/null \
    || systemctl --user try-restart assistant-zalo.service 2>/dev/null \
    || true
  sleep 3
}

restart_hermes() {
  log "restart hermes replicas (+ ${PROXY_CTR} if present) [ZALO_WATCH_RESTART_HERMES=1]"
  $SUDO docker restart "$PROXY_CTR" 2>/dev/null || true
  # Scale-safe: restart all compose hermes containers (assistant-hermes-1, …)
  local ids
  ids="$($SUDO docker ps -aq --filter "name=hermes" 2>/dev/null || true)"
  if [[ -n "$ids" ]]; then
    # shellcheck disable=SC2086
    $SUDO docker restart $ids >/dev/null 2>&1 || true
  else
    $SUDO docker restart "${HERMES_CONTAINER:-hermes}" 2>/dev/null \
      || $SUDO docker restart nh-hermes 2>/dev/null \
      || true
  fi
  sleep 5
}

health_json() {
  curl -sf -m 5 "$HEALTH_URL" 2>/dev/null || true
}

main() {
  read_state
  local raw logged sse dead
  raw="$(health_json)"
  if [[ -z "$raw" ]]; then
    log "bridge health unreachable → restart bridge"
    if ! in_cooldown "$BRIDGE_COOLDOWN_S"; then
      restart_bridge
      mark_cooldown
      LAST_ACTION="restart_bridge"
      SSE_MISS=0
      write_state
    fi
    exit 0
  fi

  logged="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print("1" if d.get("loggedIn") is True or d.get("ownId") else "0")' "$raw" 2>/dev/null || echo 0)"
  dead="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print("1" if d.get("sessionDead") is True else "0")' "$raw" 2>/dev/null || echo 0)"
  sse="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print(int(d.get("sseClients") or d.get("sseClientCount") or 0))' "$raw" 2>/dev/null || echo 0)"

  if [[ "$dead" == "1" ]]; then
    log "sessionDead=true — need manual login-zalo (cannot auto QR)"
    SSE_MISS=0
    LAST_ACTION="session_dead"
    write_state
    exit 0
  fi

  if [[ "$logged" != "1" ]]; then
    log "bridge not logged in — skip (run login-zalo.sh)"
    SSE_MISS=0
    write_state
    exit 0
  fi

  if [[ "$sse" -lt 1 ]]; then
    SSE_MISS=$((SSE_MISS + 1))
    log "loggedIn but sseClients=${sse} (miss ${SSE_MISS}/${SSE_MISS_LIMIT}) restart_hermes=${RESTART_HERMES}"
    if [[ "$SSE_MISS" -ge "$SSE_MISS_LIMIT" ]]; then
      if ! in_cooldown "$SSE_COOLDOWN_S"; then
        restart_bridge
        if [[ "$RESTART_HERMES" == "1" ]]; then
          sleep 2
          restart_hermes
          LAST_ACTION="restart_hermes_sse0"
        else
          # Default: never bounce Hermes — wait for adapter SSE reconnect
          log "sse=0: bridge restarted only (set ZALO_WATCH_RESTART_HERMES=1 to also restart hermes)"
          LAST_ACTION="restart_bridge_sse0"
        fi
        mark_cooldown
        SSE_MISS=0
      else
        log "sse=0 heal skipped (cooldown ${SSE_COOLDOWN_S}s)"
      fi
    fi
    write_state
    exit 0
  fi

  # Healthy
  if [[ "$SSE_MISS" -gt 0 || "$LAST_ACTION" == restart_* ]]; then
    log "OK sseClients=${sse} (recovered)"
  fi
  SSE_MISS=0
  LAST_ACTION="ok"
  write_state
}

main "$@"
