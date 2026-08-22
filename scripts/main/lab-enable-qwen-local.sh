#!/usr/bin/env bash
# Enable local Qwen (Ollama qwen2.5:7b) for lab — no DashScope key required.
# Usage: bash scripts/main/lab-enable-qwen-local.sh
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT"
# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source <(tr -d '\r' < .env) && set +a

OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
OLLAMA_HOST_URL="${OLLAMA_HOST_URL:-http://127.0.0.1:11434}"
OLLAMA_DOCKER_URL="${OLLAMA_DOCKER_URL:-http://host.docker.internal:11434}"

log() { echo "==> $*"; }

if ! command -v ollama >/dev/null 2>&1; then
  log "install Ollama"
  curl -fsSL https://ollama.com/install.sh | sh
fi
systemctl enable ollama 2>/dev/null || true
systemctl start ollama 2>/dev/null || true
sleep 2

if ! curl -fsS -m 8 "${OLLAMA_HOST_URL}/api/tags" 2>/dev/null | grep -q "${OLLAMA_MODEL}"; then
  log "pull ${OLLAMA_MODEL}"
  ollama pull "${OLLAMA_MODEL}"
fi

upsert() {
  local k="$1" v="$2"
  if grep -q "^${k}=" .env 2>/dev/null; then
    sed -i "s|^${k}=.*|${k}=${v}|" .env
  else
    echo "${k}=${v}" >> .env
  fi
}

upsert ENABLE_QWEN 1
upsert OLLAMA_BASE_URL "${OLLAMA_DOCKER_URL}"
upsert OLLAMA_MODEL "${OLLAMA_MODEL}"

log "first-setup-omnirouter (local Qwen combos)"
bash run.sh first-setup-omnirouter

docker restart router-worker omni-router assistant-hermes-1 2>/dev/null || true
sleep 10

log "verify model-router → Ollama"
curl -fsS -m 120 -X POST http://127.0.0.1:8096/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"hermes","messages":[{"role":"user","content":"reply OK"}],"max_tokens":8}' \
  | head -c 200 || echo "WARN: router chat probe failed"

echo "OK: local Qwen enabled (${OLLAMA_MODEL} via ${OLLAMA_DOCKER_URL})"
