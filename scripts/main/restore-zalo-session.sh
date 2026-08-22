#!/usr/bin/env bash
# Restore Zalo bridge credentials from durable backup (skip QR on redeploy).
set -euo pipefail
ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a
DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
PORT="${ZALO_PLUGIN_PORT:-8787}"
DEST_DIR="${ZALO_DATA_DIR:-/home/tn/.hermes-zalo}"
# Prefer durable backup; fall back to common paths.
SRC="${DATA_DIR}/zalo-session-backup/credentials.json"
if [[ ! -f "$SRC" ]]; then
  echo "ERROR: missing ${SRC} — run backup-zalo-session.sh after a successful QR login" >&2
  exit 1
fi
mkdir -p "$DEST_DIR"
# Also restore into $HOME for the invoking user when different from tn.
cp -a "$SRC" "${DEST_DIR}/credentials.json"
chmod 600 "${DEST_DIR}/credentials.json" 2>/dev/null || true
if [[ -n "${HOME:-}" && "${HOME}/.hermes-zalo" != "$DEST_DIR" ]]; then
  mkdir -p "${HOME}/.hermes-zalo"
  cp -a "$SRC" "${HOME}/.hermes-zalo/credentials.json"
  chmod 600 "${HOME}/.hermes-zalo/credentials.json" 2>/dev/null || true
fi
systemctl --user try-restart com.hermes.zaloplugin.service 2>/dev/null \
  || systemctl --user try-restart assistant-zalo.service 2>/dev/null \
  || true
sleep 3
echo "--- health ---"
curl -fsS -m 8 "http://127.0.0.1:${PORT}/health" || true
echo
echo "OK: restored credentials → ${DEST_DIR}/credentials.json"
echo "NEXT: docker restart assistant-hermes-1 zalo-api  (or: bash run.sh up)"
