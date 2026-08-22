#!/usr/bin/env bash
# Backup Zalo bridge credentials so a later clean redeploy can skip QR.
# Source of truth at runtime: ~/.hermes-zalo/credentials.json
# Backup (durable): $ASSISTANT_DATA_DIR/zalo-session-backup/
set -euo pipefail
ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a
DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
SRC_DIR="${ZALO_DATA_DIR:-${HOME}/.hermes-zalo}"
DEST="${DATA_DIR}/zalo-session-backup"
PORT="${ZALO_PLUGIN_PORT:-8787}"

mkdir -p "$DEST"
# Prefer explicit ZALO_DATA_DIR, then common lab home for user tn, then $HOME.
CANDIDATES=(
  "${ZALO_DATA_DIR:+${ZALO_DATA_DIR}/credentials.json}"
  "/home/tn/.hermes-zalo/credentials.json"
  "${HOME}/.hermes-zalo/credentials.json"
  "${SRC_DIR}/credentials.json"
)
SRC=""
for c in "${CANDIDATES[@]}"; do
  [[ -n "$c" && -f "$c" ]] || continue
  SRC="$c"
  break
done
if [[ -z "$SRC" ]]; then
  echo "ERROR: missing credentials.json — login first (bash scripts/main/login-zalo.sh)" >&2
  exit 1
fi
cp -a "$SRC" "${DEST}/credentials.json"
# health snapshot (no secrets)
curl -fsS -m 5 "http://127.0.0.1:${PORT}/health" >"${DEST}/health.json" 2>/dev/null || true
chmod 600 "${DEST}/credentials.json" 2>/dev/null || true
echo "OK: backed up Zalo session → ${DEST}/credentials.json"
echo "    restore later: bash scripts/main/restore-zalo-session.sh"
