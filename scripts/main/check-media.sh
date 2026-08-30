#!/usr/bin/env bash
# Smoke-check Media|File worker services (localhost binds).
# Run after: WORKER_MEDIA_FILE=active bash run.sh up
set -euo pipefail

fail=0
check() {
  local name="$1" url="$2"
  if curl -fsS -m 5 "$url" >/dev/null 2>&1; then
    echo "OK  ${name}  ${url}"
  else
    echo "FAIL ${name}  ${url}"
    fail=1
  fi
}

echo "WORKER_MEDIA_FILE=${WORKER_MEDIA_FILE:-inactive} ENABLE_MEDIA_FILE=${ENABLE_MEDIA_FILE:-inactive}"
check dispatcher "http://127.0.0.1:${DISPATCHER_PORT:-8090}/health"
check ocr        "http://127.0.0.1:${OCR_PORT:-8091}/health"
check jobs       "http://127.0.0.1:${JOBS_PORT:-8104}/health"
check searxng    "http://127.0.0.1:${SEARXNG_PORT:-8888}/healthz"

# Optional: paid keys present (empty = SearXNG-only path)
if [[ -n "${TAVILY_API_KEY:-}" ]]; then echo "OK  TAVILY_API_KEY set"; else echo "INFO TAVILY_API_KEY empty (SearXNG fallback)"; fi
if [[ -n "${FIRECRAWL_API_KEY:-}" ]]; then echo "OK  FIRECRAWL_API_KEY set"; else echo "INFO FIRECRAWL_API_KEY empty"; fi

if [[ "$fail" -ne 0 ]]; then
  echo "Media|File smoke failed — check: bash run.sh ps"
  exit 1
fi
echo "OK: Media|File smoke passed"

