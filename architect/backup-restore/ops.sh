#!/usr/bin/env bash
# DR entry — wraps lib/backup.sh when present.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export ROOT
export BACKUP_DIR="${BACKUP_DIR:-/data/assistant/backups}"
export LC_ALL=C.UTF-8
# shellcheck source=lib/common.sh
source "${ROOT}/architect/backup-restore/lib/common.sh" 2>/dev/null || true
# shellcheck source=lib/backup.sh
if [[ -f "${ROOT}/architect/backup-restore/lib/backup.sh" ]]; then
  source "${ROOT}/architect/backup-restore/lib/backup.sh"
fi
cmd="${1:-help}"
shift || true
case "$cmd" in
  backup)
    if declare -F assistant_backup_all >/dev/null 2>&1; then
      assistant_backup_all
    else
      mkdir -p "$BACKUP_DIR"
      stamp="$(date +%Y%m%d_%H%M%S)"
      mkdir -p "${BACKUP_DIR}/${stamp}"
      echo "${stamp}" > "${BACKUP_DIR}/LATEST"
      echo "backup stub stamp=${stamp} dir=${BACKUP_DIR}/${stamp}"
      echo "(wire lib/backup.sh paths to /data/assistant for full DR)"
    fi
    ;;
  restore)
    if declare -F assistant_restore_all >/dev/null 2>&1; then
      assistant_restore_all "$@"
    else
      echo "restore stub — align backup.sh with assistant paths; stamp=${1:-LATEST}"
    fi
    ;;
  verify)
    if declare -F assistant_verify_backup >/dev/null 2>&1; then
      assistant_verify_backup "$@"
    else
      latest="$(cat "${BACKUP_DIR}/LATEST" 2>/dev/null || echo "")"
      echo "verify stub BACKUP_DIR=${BACKUP_DIR} LATEST=${latest:-none}"
      [[ -n "$latest" && -d "${BACKUP_DIR}/${latest}" ]] || exit 1
    fi
    ;;
  migrate)
    latest="$(cat "${BACKUP_DIR}/LATEST" 2>/dev/null || true)"
    [[ -n "$latest" ]] || { echo "no LATEST — run backup first"; exit 1; }
    out="${BACKUP_DIR}/migrate_${latest}.tgz"
    tar -C "${BACKUP_DIR}" -czf "$out" "$latest" LATEST
    echo "migrate pack → ${out}"
    echo "On new host: extract into BACKUP_DIR then: bash run.sh restore ${latest}"
    ;;
  *)
    echo "usage: ops.sh backup|restore|verify|migrate"
    ;;
esac
