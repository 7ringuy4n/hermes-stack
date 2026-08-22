#!/usr/bin/env bash
# Heal Zalo SSE after restore / owner-lock drift (component: ENABLE_ZALO=1).
# Clears stale zalo_owner election files, restarts zalo-proxy + Hermes replicas
# so exactly one replica can re-attach SSE.
#
# Called automatically by setup-zalo.sh / login-zalo.sh after QR success.
# Re-run manually anytime Hermes loses bridge (sseClients: 0):
#   bash scripts/main/heal-zalo-sse.sh
set -euo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a
[[ -f /data/assistant/.env ]] && set -a && source <(tr -d '\r' < /data/assistant/.env) && set +a

DATA="${ASSISTANT_DATA_DIR:-${HERMES_DATA_DIR:-/data/assistant}}"
PROXY_CTR="${ZALO_PROXY_CONTAINER:-zalo-proxy}"
if [[ "$(id -u)" -ne 0 ]]; then SUDO=sudo; else SUDO=; fi

log() { echo "$(date -Is) heal-zalo-sse: $*"; }

docker_cmd() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  elif [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" && "$(id -u)" -ne 0 ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S docker "$@"
  else
    $SUDO docker "$@"
  fi
}

case "${ENABLE_ZALO:-0}" in
  1) ;;
  *)
    log "ENABLE_ZALO!=1 — skip"
    exit 0
    ;;
esac

log "clear stale Zalo owner lock under ${DATA}"
$SUDO rm -rf "${DATA}/zalo_owner" "${DATA}/zalo_owner.lock" 2>/dev/null || true

# Compose proxy (High) — preferred over host systemd bridge units
if docker_cmd ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$PROXY_CTR"; then
  log "restart ${PROXY_CTR}"
  docker_cmd restart "$PROXY_CTR" >/dev/null 2>&1 || true
fi

ids="$(docker_cmd ps -aq --filter "name=hermes" 2>/dev/null || true)"
if [[ -n "$ids" ]]; then
  log "restart Hermes replicas for fresh Zalo owner election"
  # shellcheck disable=SC2086
  docker_cmd restart $ids >/dev/null 2>&1 || true
else
  log "WARN: no hermes containers found"
fi

sleep 5
port="${ZALO_PLUGIN_PORT:-8787}"
# Wait for host bridge before Hermes SSE reconnects (avoids connect storm to dead :8787).
for _i in $(seq 1 20); do
  if curl -sf -m 3 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
    break
  fi
  if [[ "$_i" -eq 1 ]] && [[ -f "${ROOT}/scripts/main/patch_zalo_bridge_inject.py" ]]; then
    log "bridge not ready — patch/restart host unit"
    ZALO_BRIDGE_FORCE_RESTART=1 $SUDO python3 "${ROOT}/scripts/main/patch_zalo_bridge_inject.py" \
      >/dev/null 2>&1 || true
  fi
  sleep 1
done
health="$(curl -sf -m 5 "http://127.0.0.1:${port}/health" 2>/dev/null || true)"
if [[ -n "$health" ]]; then
  log "bridge health: ${health}"
else
  log "WARN: bridge health unreachable on :${port} (tunnel or publish may be required)"
fi
log "done"
