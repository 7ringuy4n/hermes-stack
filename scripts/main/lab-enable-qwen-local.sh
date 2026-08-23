#!/usr/bin/env bash
# Enable local Qwen (Ollama) for lab — no DashScope key required.
# Aligns OLLAMA_MODEL to a pulled tag, fills Omni hermes combo with that member,
# then recreates router-worker.
# Usage: bash scripts/main/lab-enable-qwen-local.sh
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT"
# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source <(tr -d '\r' < .env) && set +a

OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3.5:2b-instruct}"
OLLAMA_HOST_URL="${OLLAMA_HOST_URL:-http://127.0.0.1:11434}"
OLLAMA_DOCKER_URL="${OLLAMA_DOCKER_URL:-http://host.docker.internal:11434}"

log() { echo "==> $*"; }

upsert() {
  local k="$1" v="$2"
  if grep -q "^${k}=" .env 2>/dev/null; then
    sed -i "s|^${k}=.*|${k}=${v}|" .env
  else
    echo "${k}=${v}" >> .env
  fi
}

rc=0
bash "${ROOT}/scripts/main/ensure-ollama.sh" || rc=$?
if [[ "$rc" -eq 1 ]]; then
  log "FAIL ensure-ollama"
  exit 1
fi
# exit 3 = OLLAMA_MODEL realigned in .env — reload
if [[ "$rc" -eq 3 || "$rc" -eq 0 || "$rc" -eq 2 ]]; then
  set -a && source <(tr -d '\r' < .env) && set +a
  OLLAMA_MODEL="${OLLAMA_MODEL}"
fi

upsert ENABLE_QWEN 1
upsert ENABLE_QWEN_THINKING 1
upsert OLLAMA_BASE_URL "${OLLAMA_DOCKER_URL}"
upsert OLLAMA_MODEL "${OLLAMA_MODEL}"
# Let Omni hermes combo RR; router still keeps Ollama as last hop after 503.
upsert OMNIROUTER_FAILOVER_MODELS ""
upsert OMNIROUTER_ROTATE_ATTEMPTS 2

log "first-setup-omnirouter (hermes combo → local Ollama via Omni API)"
bash run.sh first-setup-omnirouter

docker restart router-worker omni-router assistant-hermes-1 2>/dev/null || true
cd "$ROOT"
docker compose -f docker/docker-compose.yml up -d router-worker 2>/dev/null || \
  docker compose up -d router-worker 2>/dev/null || true
sleep 10

log "verify model-router → Omni hermes → Ollama"
curl -fsS -m 120 -X POST http://127.0.0.1:8096/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"hermes","messages":[{"role":"user","content":"reply OK"}],"max_tokens":8}' \
  | head -c 300 || echo "WARN: router chat probe failed"

echo "OK: local Qwen enabled (${OLLAMA_MODEL} via ${OLLAMA_DOCKER_URL}; Omni hermes combo)"
