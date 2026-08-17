#!/usr/bin/env bash
# Self-heal Zalo channel (bridge + Hermes SSE owner).
# Intended as systemd timer (every ~1–2 min) when ENABLE_ZALO=1.
#
# Signals:
#   - bridge /health unreachable → restart host Zalo unit and/or zalo-proxy
#   - loggedIn but sseClients==0 → after miss limit: clear zalo_owner lock,
#     restart zalo-proxy + Hermes (required after backup/restore when owner
#     file points at a dead container id). Cooldown avoids restart storms.
#   - ZALO_WATCH_RESTART_HERMES=0 disables Hermes bounce (bridge/proxy only)
set -euo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a
[[ -f /data/assistant/.env ]] && set -a && source <(tr -d '\r' < /data/assistant/.env) && set +a

PORT="${ZALO_PLUGIN_PORT:-8787}"
HEALTH_URL="${ZALO_WATCH_HEALTH_URL:-http://127.0.0.1:${PORT}/health}"
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
SSE_MISS_LIMIT="${ZALO_WATCH_SSE_MISS:-8}"
SSE_COOLDOWN_S="${ZALO_WATCH_SSE_COOLDOWN:-900}"
BRIDGE_COOLDOWN_S="${ZALO_WATCH_BRIDGE_COOLDOWN:-90}"
# Default ON: sse=0 after restore is almost always a dead Zalo owner lock / Hermes
RESTART_HERMES="${ZALO_WATCH_RESTART_HERMES:-1}"
CLEAR_OWNER="${ZALO_WATCH_CLEAR_OWNER:-1}"
PROXY_CTR="${ZALO_PROXY_CONTAINER:-zalo-proxy}"
HEAL_SCRIPT="${ROOT}/scripts/main/heal-zalo-sse.sh"
if [[ "$(id -u)" -ne 0 ]]; then SUDO=sudo; else SUDO=; fi

if ! mkdir -p "$STATE_DIR" 2>/dev/null; then
  $SUDO mkdir -p "$STATE_DIR"
  $SUDO chown "$(id -u):$(id -g)" "$STATE_DIR" 2>/dev/null || true
fi
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

clear_owner_lock() {
  case "${CLEAR_OWNER}" in
    1|true|TRUE|yes|YES) ;;
    *) return 0 ;;
  esac
  log "clear stale zalo_owner under ${_data_root}"
  $SUDO rm -rf "${_data_root}/zalo_owner" "${_data_root}/zalo_owner.lock" 2>/dev/null || true
}

restart_bridge() {
  log "restart host Zalo bridge unit (if any)"
  systemctl --user try-restart com.hermes.zaloplugin.service 2>/dev/null \
    || systemctl --user try-restart assistant-zalo.service 2>/dev/null \
    || true
  if $SUDO docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$PROXY_CTR"; then
    log "restart ${PROXY_CTR}"
    $SUDO docker restart "$PROXY_CTR" >/dev/null 2>&1 || true
  fi
  sleep 3
}

restart_hermes() {
  log "restart Hermes replicas for Zalo SSE re-attach"
  local ids
  ids="$($SUDO docker ps -aq --filter "name=hermes" 2>/dev/null || true)"
  if [[ -n "$ids" ]]; then
    # shellcheck disable=SC2086
    $SUDO docker restart $ids >/dev/null 2>&1 || true
  else
    $SUDO docker restart "${HERMES_CONTAINER:-hermes}" 2>/dev/null || true
  fi
  sleep 5
}

heal_sse_zero() {
  if [[ -x "$HEAL_SCRIPT" ]] || [[ -f "$HEAL_SCRIPT" ]]; then
    log "run heal-zalo-sse.sh"
    bash "$HEAL_SCRIPT" || true
    return 0
  fi
  clear_owner_lock
  restart_bridge
  case "${RESTART_HERMES}" in
    1|true|TRUE|yes|YES)
      sleep 2
      restart_hermes
      ;;
    *)
      log "sse=0: owner cleared + bridge restarted (set ZALO_WATCH_RESTART_HERMES=1 to bounce Hermes)"
      ;;
  esac
}

health_json() {
  curl -sf -m 5 "$HEALTH_URL" 2>/dev/null || true
}

main() {
  read_state
  # Crash recovery: a stopped proxy still leaves host bridge /health up, so
  # SSE/Hermes look "fine" while the Docker hop is dead. Start it first.
  if $SUDO docker inspect -f '{{.State.Running}}' "$PROXY_CTR" 2>/dev/null | grep -qx false; then
    log "proxy not running → start ${PROXY_CTR}"
    $SUDO docker start "$PROXY_CTR" >/dev/null 2>&1 || true
    sleep 2
  fi
  local raw logged sse dead
  raw="$(health_json)"
  if [[ -z "$raw" ]]; then
    log "bridge health unreachable → restart bridge/proxy"
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

  case "$dead" in
    1)
      log "sessionDead=true — need manual login-zalo (cannot auto QR)"
      SSE_MISS=0
      LAST_ACTION="session_dead"
      write_state
      exit 0
      ;;
  esac

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
        heal_sse_zero
        mark_cooldown
        LAST_ACTION="heal_sse0"
        SSE_MISS=0
      else
        log "sse=0 heal skipped (cooldown ${SSE_COOLDOWN_S}s)"
      fi
    fi
    write_state
    exit 0
  fi

  if [[ "$SSE_MISS" -gt 0 || "$LAST_ACTION" == restart_* || "$LAST_ACTION" == heal_* ]]; then
    log "OK sseClients=${sse} (recovered)"
  fi
  SSE_MISS=0
  LAST_ACTION="ok"
  write_state
}

main "$@"
