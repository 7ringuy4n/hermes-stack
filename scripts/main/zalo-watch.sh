#!/usr/bin/env bash
# Self-heal Zalo channel: bridge + hermes SSE.
# Intended as systemd timer (every ~1–2 min) when ENABLE_ZALO=1.
#
# Signals:
#   - bridge /health unreachable or sessionDead → restart user Zalo unit
#   - loggedIn but sseClients==0 for N polls → docker restart hermes (+ zalo-proxy)
# Users never see backend; we only recover so DMs work again.
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a

PORT="${ZALO_PLUGIN_PORT:-8787}"
HEALTH_URL="${ZALO_WATCH_HEALTH_URL:-http://127.0.0.1:${PORT}/health}"
STATE_DIR="${ASSISTANT_DATA_DIR:-${HERMES_DATA_DIR:-/data/assistant}}/watch"
STATE_FILE="${STATE_DIR}/zalo-watch.state"
COOLDOWN_FILE="${STATE_DIR}/zalo-watch.cooldown"
SSE_MISS_LIMIT="${ZALO_WATCH_SSE_MISS:-2}"
HERMES_CTR="${HERMES_CONTAINER:-hermes}"
PROXY_CTR="${ZALO_PROXY_CONTAINER:-zalo-proxy}"
if [[ "$(id -u)" -ne 0 ]]; then SUDO=sudo; else SUDO=; fi

mkdir -p "$STATE_DIR"
touch "$STATE_FILE"

log() { echo "$(date -Is) zalo-watch: $*"; }

read_state() {
  SSE_MISS=0
  LAST_ACTION=""
  # shellcheck disable=SC1090
  [[ -f "$STATE_FILE" ]] && source "$STATE_FILE" || true
  SSE_MISS="${SSE_MISS:-0}"
}

write_state() {
  cat >"$STATE_FILE" <<EOF
SSE_MISS=${SSE_MISS:-0}
LAST_ACTION=$(printf '%q' "${LAST_ACTION:-}")
LAST_TS=$(date +%s)
EOF
}

in_cooldown() {
  local sec="${1:-120}"
  [[ -f "$COOLDOWN_FILE" ]] || return 1
  local then now
  then="$(cat "$COOLDOWN_FILE" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  [[ $((now - then)) -lt "$sec" ]]
}

mark_cooldown() { date +%s >"$COOLDOWN_FILE"; }

restart_bridge() {
  log "restart host Zalo bridge unit"
  systemctl --user try-restart com.hermes.zaloplugin.service 2>/dev/null \
    || systemctl --user try-restart assistant-zalo.service 2>/dev/null \
    || true
  sleep 3
}

restart_hermes() {
  log "restart ${HERMES_CTR} (+ ${PROXY_CTR} if present)"
  $SUDO docker restart "$PROXY_CTR" 2>/dev/null || true
  $SUDO docker restart "$HERMES_CTR" 2>/dev/null \
    || $SUDO docker restart hermes 2>/dev/null \
    || true
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
    if ! in_cooldown 90; then
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
    log "loggedIn but sseClients=${sse} (miss ${SSE_MISS}/${SSE_MISS_LIMIT})"
    if [[ "$SSE_MISS" -ge "$SSE_MISS_LIMIT" ]]; then
      if ! in_cooldown 120; then
        # Bridge first, then hermes (lab order)
        restart_bridge
        sleep 2
        restart_hermes
        mark_cooldown
        LAST_ACTION="restart_hermes_sse0"
        SSE_MISS=0
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
