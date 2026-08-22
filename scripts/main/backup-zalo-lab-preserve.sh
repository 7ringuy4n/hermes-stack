#!/usr/bin/env bash
# Lab preserve: Zalo session + postgres zalo_entities + allowlists (size-guarded).
# Usage: bash scripts/main/backup-zalo-lab-preserve.sh [dest_dir]
set -euo pipefail
ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a
DEST="${1:-/home/tn/zalo-lab-preserve}"
DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
MAX_ALLOWLIST_BYTES=512

mkdir -p "$DEST"
bash "${ROOT}/scripts/main/backup-zalo-session.sh"
cp -a "${DATA_DIR}/zalo-session-backup/credentials.json" "${DEST}/credentials.json"
chmod 600 "${DEST}/credentials.json" 2>/dev/null || true

for f in zalo_admin_users.txt zalo_allowed_users.txt zalo_allowed_threads.txt; do
  src="${DATA_DIR}/${f}"
  [[ -f "$src" ]] || continue
  size=$(wc -c <"$src" 2>/dev/null || echo 9999)
  if [[ "$size" -gt "$MAX_ALLOWLIST_BYTES" ]]; then
    echo "WARN: skip ${f} (${size} bytes > ${MAX_ALLOWLIST_BYTES})"
    continue
  fi
  if head -c 1 "$src" | grep -q '{' 2>/dev/null || grep -q '"cookies"' "$src" 2>/dev/null; then
    echo "WARN: skip ${f} (looks like credentials.json)"
    continue
  fi
  cp -a "$src" "${DEST}/${f}"
done

PG=$(docker ps -q --filter name=^postgres$ 2>/dev/null | head -1 || true)
if [[ -n "$PG" ]]; then
  U="${MEMORY_DB_USER:-hermes}"
  D="${MEMORY_DB_NAME:-hermes_memory}"
  docker exec "$PG" pg_dump -U "$U" -d "$D" -t zalo_entities --data-only \
    >"${DEST}/zalo_entities.sql" 2>/dev/null || echo "WARN: zalo_entities dump failed"
fi

echo "OK: lab preserve → ${DEST}"
