#!/usr/bin/env bash
# Copy Hermes Zalo adapter SoT → shared data dir (what containers mount at /opt/data/plugins/zalo).
# git pull updates hermes/main/plugins only; without this step replicas keep stale Python.
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
source "${ROOT}/scripts/main/zalo-common.sh"

PLUGIN_SRC="${ROOT}/hermes/main/plugins/zalo"
PLUGIN_DIR="${HERMES_SHARED_DATA}/plugins/zalo"
WEB_PLUGIN_SRC="${ROOT}/hermes/main/plugins/web/router_worker"
WEB_PLUGIN_DIR="${HERMES_SHARED_DATA}/plugins/web/router_worker"

if [[ ! -d "$PLUGIN_SRC" ]]; then
  echo "WARN: missing ${PLUGIN_SRC} — skip zalo plugin sync" >&2
  exit 0
fi

# Keep the stack-owned Hermes web provider beside the Zalo plugin. Without its
# register() module the configured provider name exists in YAML but native
# web_search cannot resolve it at runtime.
if [[ -d "$WEB_PLUGIN_SRC" ]]; then
  mkdir -p "$(dirname "$WEB_PLUGIN_DIR")" 2>/dev/null || $ZALO_SUDO mkdir -p "$(dirname "$WEB_PLUGIN_DIR")"
  if [[ -w "$(dirname "$WEB_PLUGIN_DIR")" ]] && { [[ ! -e "$WEB_PLUGIN_DIR" ]] || [[ -w "$WEB_PLUGIN_DIR" ]]; }; then
    rm -rf "$WEB_PLUGIN_DIR"
    cp -a "$WEB_PLUGIN_SRC" "$WEB_PLUGIN_DIR"
  else
    $ZALO_SUDO rm -rf "$WEB_PLUGIN_DIR"
    $ZALO_SUDO cp -a "$WEB_PLUGIN_SRC" "$WEB_PLUGIN_DIR"
  fi
fi

zalo_log "sync zalo plugins ${PLUGIN_SRC} → ${PLUGIN_DIR}"
parent_dir="$(dirname "$PLUGIN_DIR")"
mkdir -p "$parent_dir" 2>/dev/null || $ZALO_SUDO mkdir -p "$parent_dir"
if [[ -w "$parent_dir" ]] && { [[ ! -e "$PLUGIN_DIR" ]] || [[ -w "$PLUGIN_DIR" ]]; }; then
  rm -rf "$PLUGIN_DIR"
  cp -a "$PLUGIN_SRC" "$PLUGIN_DIR"
else
  $ZALO_SUDO rm -rf "$PLUGIN_DIR"
  $ZALO_SUDO cp -a "$PLUGIN_SRC" "$PLUGIN_DIR"
  $ZALO_SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "${HERMES_SHARED_DATA}/plugins" 2>/dev/null || true
fi

# Hermes replicas keep a per-container plugins/ copy (hermes-replica-entry.sh).
# Overlay SoT into every replica dir so a restart is not required for hot fixes.
if [[ -d "${HERMES_SHARED_DATA}/replicas" ]]; then
  for rep_plugins in "${HERMES_SHARED_DATA}"/replicas/*/plugins; do
    [[ -d "$rep_plugins" ]] || continue
    if [[ -w "$(dirname "$rep_plugins")" ]]; then
      mkdir -p "$rep_plugins"
      cp -a "${PLUGIN_DIR}/." "$rep_plugins/" 2>/dev/null || true
      mkdir -p "$rep_plugins/web"
      rm -rf "$rep_plugins/web/router_worker"
      cp -a "$WEB_PLUGIN_DIR" "$rep_plugins/web/router_worker" 2>/dev/null || true
    else
      $ZALO_SUDO mkdir -p "$rep_plugins"
      $ZALO_SUDO cp -a "${PLUGIN_DIR}/." "$rep_plugins/" 2>/dev/null || true
      $ZALO_SUDO mkdir -p "$rep_plugins/web"
      $ZALO_SUDO rm -rf "$rep_plugins/web/router_worker"
      $ZALO_SUDO cp -a "$WEB_PLUGIN_DIR" "$rep_plugins/web/router_worker" 2>/dev/null || true
    fi
  done
  zalo_log "overlay zalo plugins into Hermes replica dirs"
fi

if [[ "${SYNC_ZALO_RESTART:-1}" == "1" ]] && docker info >/dev/null 2>&1; then
  mapfile -t hermes < <(docker ps --format '{{.Names}}' 2>/dev/null | grep -E '^assistant-hermes-' || true)
  if [[ ${#hermes[@]} -gt 0 ]]; then
    zalo_log "restart Hermes replicas after plugin sync (${#hermes[@]})"
  fi
  for c in "${hermes[@]}"; do
    docker restart "$c" >/dev/null 2>&1 || true
  done
elif [[ "${SYNC_ZALO_RESTART:-1}" != "1" ]]; then
  zalo_log "skip Hermes restart; caller will recreate the selected services"
fi

echo "OK: zalo plugins synced"
