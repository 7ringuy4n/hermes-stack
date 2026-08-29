#!/usr/bin/env bash
# Copy Hermes Zalo adapter SoT → shared data dir (what containers mount at /opt/data/plugins/zalo).
# git pull updates hermes/main/plugins only; without this step replicas keep stale Python.
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
source "${ROOT}/scripts/main/zalo-common.sh"

PLUGIN_SRC="${ROOT}/hermes/main/plugins/zalo"
PLUGIN_DIR="${HERMES_SHARED_DATA}/plugins/zalo"

if [[ ! -d "$PLUGIN_SRC" ]]; then
  echo "WARN: missing ${PLUGIN_SRC} — skip zalo plugin sync" >&2
  exit 0
fi

zalo_log "sync zalo plugins ${PLUGIN_SRC} → ${PLUGIN_DIR}"
$ZALO_SUDO mkdir -p "$(dirname "$PLUGIN_DIR")"
$ZALO_SUDO rm -rf "$PLUGIN_DIR"
$ZALO_SUDO cp -a "$PLUGIN_SRC" "$PLUGIN_DIR"
$ZALO_SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "${HERMES_SHARED_DATA}/plugins" 2>/dev/null || true

# Hermes replicas keep a per-container plugins/ copy (hermes-replica-entry.sh).
# Overlay SoT into every replica dir so a restart is not required for hot fixes.
if [[ -d "${HERMES_SHARED_DATA}/replicas" ]]; then
  for rep_plugins in "${HERMES_SHARED_DATA}"/replicas/*/plugins; do
    [[ -d "$rep_plugins" ]] || continue
    $ZALO_SUDO mkdir -p "$rep_plugins"
    $ZALO_SUDO cp -a "${PLUGIN_DIR}/." "$rep_plugins/" 2>/dev/null || true
  done
  zalo_log "overlay zalo plugins into Hermes replica dirs"
fi

if docker info >/dev/null 2>&1; then
  mapfile -t hermes < <(docker ps --format '{{.Names}}' 2>/dev/null | grep -E '^assistant-hermes-' || true)
  if [[ ${#hermes[@]} -gt 0 ]]; then
    zalo_log "restart Hermes replicas after plugin sync (${#hermes[@]})"
  fi
  for c in "${hermes[@]}"; do
    docker restart "$c" >/dev/null 2>&1 || true
  done
fi

echo "OK: zalo plugins synced"
