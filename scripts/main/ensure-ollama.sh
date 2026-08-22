#!/usr/bin/env bash
# Ensure host Ollama is running and reachable (ENABLE_QWEN + OLLAMA_BASE_URL).
# Used by run.sh, stack-watch, post-lab-restore, lab-enable-qwen-local.
# Exit 0 when host + (optional) router-worker can reach Ollama; 1 on hard failure.
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a
[[ -f /data/assistant/.env ]] && set -a && source <(tr -d '\r' < /data/assistant/.env) && set +a

OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:4b}"
OLLAMA_HOST_URL="${OLLAMA_HOST_URL:-http://127.0.0.1:11434}"
OLLAMA_DOCKER_URL="${OLLAMA_DOCKER_URL:-${OLLAMA_BASE_URL:-http://host.docker.internal:11434}}"

log() { echo "$(date -Is) ensure-ollama: $*"; }

host_ok() {
  curl -fsS -m 8 "${OLLAMA_HOST_URL}/api/tags" 2>/dev/null | grep -q '"models"' \
    || curl -fsS -m 8 "${OLLAMA_HOST_URL}/api/tags" 2>/dev/null | grep -q "${OLLAMA_MODEL}"
}

docker_ok() {
  local ctr="${OLLAMA_PROBE_CONTAINER:-router-worker}"
  if ! docker inspect -f '{{.State.Running}}' "$ctr" 2>/dev/null | grep -qx true; then
    return 0
  fi
  docker exec "$ctr" python3 -c "
import urllib.request, sys
url = '${OLLAMA_DOCKER_URL%/}/api/tags'
try:
    with urllib.request.urlopen(url, timeout=8) as r:
        sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

if [[ "${ENABLE_QWEN:-0}" != "1" && -z "${OLLAMA_BASE_URL:-}" ]]; then
  log "skip (ENABLE_QWEN off and no OLLAMA_BASE_URL)"
  exit 0
fi

if ! command -v ollama >/dev/null 2>&1; then
  log "install Ollama"
  curl -fsSL https://ollama.com/install.sh | sh
fi

systemctl enable ollama 2>/dev/null || true

# Docker reaches host via host.docker.internal — Ollama must listen beyond 127.0.0.1.
OLLAMA_LISTEN="${OLLAMA_HOST:-0.0.0.0:11434}"
dropin="/etc/systemd/system/ollama.service.d"
if [[ "$(id -u)" -eq 0 ]]; then
  mkdir -p "$dropin"
  printf '[Service]\nEnvironment=OLLAMA_HOST=%s\n' "$OLLAMA_LISTEN" >"${dropin}/hermes-docker.conf"
  systemctl daemon-reload 2>/dev/null || true
elif command -v sudo >/dev/null 2>&1; then
  sudo mkdir -p "$dropin"
  printf '[Service]\nEnvironment=OLLAMA_HOST=%s\n' "$OLLAMA_LISTEN" | sudo tee "${dropin}/hermes-docker.conf" >/dev/null
  sudo systemctl daemon-reload 2>/dev/null || true
fi

if ! systemctl is-active ollama >/dev/null 2>&1; then
  log "start ollama.service (OLLAMA_HOST=${OLLAMA_LISTEN})"
  systemctl restart ollama 2>/dev/null || systemctl start ollama 2>/dev/null || true
  sleep 2
else
  systemctl restart ollama 2>/dev/null || true
  sleep 2
fi

if ! curl -fsS -m 8 "${OLLAMA_HOST_URL}/api/tags" 2>/dev/null | grep -q "${OLLAMA_MODEL}"; then
  log "pull ${OLLAMA_MODEL}"
  ollama pull "${OLLAMA_MODEL}" || true
fi

if ! host_ok; then
  log "FAIL host Ollama unreachable at ${OLLAMA_HOST_URL}"
  exit 1
fi
log "OK host ${OLLAMA_HOST_URL} model=${OLLAMA_MODEL}"

if docker_ok; then
  log "OK docker ${OLLAMA_DOCKER_URL} via ${OLLAMA_PROBE_CONTAINER:-router-worker}"
else
  log "WARN docker cannot reach ${OLLAMA_DOCKER_URL} (router-worker may need restart after Ollama up)"
  exit 2
fi

exit 0
