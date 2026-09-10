#!/usr/bin/env bash
# Archive host journal + Docker container logs with retention (default 30d).
# Component: ENABLE_LOG_ARCHIVE=active. Admin: LOG_RETENTION_DAYS, LOG_ARCHIVE_DIR.
set -euo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a
[[ -f /data/assistant/.env ]] && set -a && source <(tr -d '\r' < /data/assistant/.env) && set +a

case "${ENABLE_LOG_ARCHIVE:-active}" in
  1|true|yes|on|active) ;;
  *) echo "log-archive: ENABLE_LOG_ARCHIVE!=active — skip"; exit 0 ;;
esac

RETENTION="${LOG_RETENTION_DAYS:-30}"
ARCHIVE_DIR="${LOG_ARCHIVE_DIR:-/data/assistant/log-archive}"
STAMP="$(date +%Y%m%d_%H%M%S)"
DAY_DIR="${ARCHIVE_DIR}/${STAMP}"
if [[ "$(id -u)" -ne 0 ]]; then SUDO=sudo; else SUDO=; fi

$SUDO mkdir -p "${DAY_DIR}/journal" "${DAY_DIR}/docker" "${DAY_DIR}/hermes"
echo "==> log-archive ${DAY_DIR} retention=${RETENTION}d"

# Host journal (last 24h slice)
if command -v journalctl >/dev/null 2>&1; then
  $SUDO journalctl --since "24 hours ago" -o short-iso > "${DAY_DIR}/journal/host-24h.log" 2>/dev/null || true
fi

# Docker container logs (running + recent)
if command -v docker >/dev/null 2>&1; then
  while read -r name; do
    [[ -z "$name" ]] && continue
    safe="$(printf '%s' "$name" | tr -c 'A-Za-z0-9._-' '_')"
    docker logs --since 24h "$name" > "${DAY_DIR}/docker/${safe}.log" 2>&1 || true
  done < <(docker ps -a --format '{{.Names}}' 2>/dev/null || true)
fi

# Hermes data logs if present
DATA="${ASSISTANT_DATA_DIR:-${HERMES_DATA_DIR:-/data/assistant}}"
if [[ -d "${DATA}/logs" ]]; then
  $SUDO tar -C "${DATA}" -czf "${DAY_DIR}/hermes/logs.tgz" logs 2>/dev/null || true
fi

# Compress day dir
$SUDO tar -C "${ARCHIVE_DIR}" -czf "${ARCHIVE_DIR}/${STAMP}.tgz" "${STAMP}" 2>/dev/null || true
$SUDO rm -rf "${DAY_DIR}"

# Retention prune
if [[ "${RETENTION}" =~ ^[0-9]+$ ]] && [[ "${RETENTION}" -gt 0 ]]; then
  find "${ARCHIVE_DIR}" -maxdepth 1 -type f -name '*.tgz' -mtime "+${RETENTION}" -print -delete 2>/dev/null || true
fi
echo "==> log-archive done"
