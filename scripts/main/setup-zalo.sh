#!/usr/bin/env bash
# Zalo setup: QR login FIRST, then bridge + adapter + zalo-api + Hermes plugin.
# On QR failure: no zalo-api, no full stack, bridge stopped.
#
# Run as deploy user (not root):
#   bash scripts/main/setup-zalo.sh
#
# Built-in fixes (current login user, not hardcoded):
#   - sudo chown -R $USER:$USER ~/.config  (zalo_ensure_config_writable)
#   - heal-zalo-sse.sh after stack install (zalo_heal_sse; script kept for later heal)
#
# Prerequisite: core stack up (bash run.sh up). Message worker optional until QR succeeds.
#
# Upstream: hermes-zalo-plugin by Cường Tuấn Nguyễn (cuongdev) — MIT
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
source "${ROOT}/scripts/main/zalo-common.sh"

PLUGIN_SRC="${ROOT}/hermes/main/plugins/zalo"
PLUGIN_DIR="${HERMES_SHARED_DATA}/plugins/zalo"

if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" && "$(id -u)" -ne 0 ]]; then
  if ! printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S -v >/dev/null 2>&1; then
    echo "ERROR: ASSISTANT_SUDO_PASSWORD rejected by sudo" >&2
    exit 1
  fi
fi

install_adapter() {
  $ZALO_SUDO mkdir -p "$(dirname "$PLUGIN_DIR")"
  if [[ -d "$PLUGIN_SRC" ]]; then
    zalo_log "copy adapter ${PLUGIN_SRC} → ${PLUGIN_DIR}"
    $ZALO_SUDO rm -rf "$PLUGIN_DIR"
    $ZALO_SUDO cp -a "$PLUGIN_SRC" "$PLUGIN_DIR"
  else
    echo "WARN: missing ${PLUGIN_SRC}" >&2
    return 1
  fi
  $ZALO_SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "${HERMES_SHARED_DATA}/plugins" 2>/dev/null || true
}

ensure_shared_config() {
  local cfg="${HERMES_SHARED_DATA}/config.yaml"
  if $ZALO_SUDO test -f "$cfg"; then
    return 0
  fi
  local seed
  seed="$($ZALO_SUDO bash -lc "ls -1dt '${HERMES_SHARED_DATA}'/replicas/*/config.yaml 2>/dev/null | head -n 1" || true)"
  if [[ -z "$seed" ]]; then
    zalo_log "create minimal shared config.yaml"
    $ZALO_SUDO tee "$cfg" >/dev/null <<'EOF'
_config_version: 13
plugins:
  enabled:
    - zalo-platform
gateway:
  platforms:
    zalo:
      enabled: true
EOF
  else
    zalo_log "seed shared config.yaml from ${seed}"
    $ZALO_SUDO cp -a "$seed" "$cfg"
  fi
  $ZALO_SUDO chown "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "$cfg" 2>/dev/null || true
  $ZALO_SUDO chmod 600 "$cfg" 2>/dev/null || true
}

enable_plugin() {
  local cfg="${HERMES_SHARED_DATA}/config.yaml"
  ensure_shared_config
  $ZALO_SUDO python3 - "$cfg" <<'PY'
from pathlib import Path
import sys

cfg = Path(sys.argv[1])
lines = cfg.read_text(encoding="utf-8", errors="replace").splitlines()
lines = [line for line in lines if line.strip() != "- zalo-platform"]

plugins_idx = None
for i, line in enumerate(lines):
    if line.strip() == "plugins:" and not line.startswith(" "):
        plugins_idx = i
        break

if plugins_idx is None:
    lines.extend(["", "plugins:", "  enabled:", "    - zalo-platform"])
else:
    end = len(lines)
    for j in range(plugins_idx + 1, len(lines)):
        line = lines[j]
        if line and not line.startswith((" ", "#")):
            end = j
            break
    enabled_idx = None
    for j in range(plugins_idx + 1, end):
        if lines[j].strip().startswith("enabled:"):
            enabled_idx = j
            break
    if enabled_idx is None:
        lines[plugins_idx + 1:plugins_idx + 1] = ["  enabled:", "    - zalo-platform"]
    else:
        stripped = lines[enabled_idx].strip()
        if stripped == "enabled: []":
            lines[enabled_idx] = "  enabled:"
            lines.insert(enabled_idx + 1, "    - zalo-platform")
        else:
            insert_at = enabled_idx + 1
            while insert_at < end and (not lines[insert_at].strip() or lines[insert_at].startswith("    - ")):
                insert_at += 1
            lines.insert(insert_at, "    - zalo-platform")

gateway_idx = None
for i, line in enumerate(lines):
    if line.strip() == "gateway:" and not line.startswith(" "):
        gateway_idx = i
        break

if gateway_idx is None:
    lines.extend(["", "gateway:", "  platforms:", "    zalo:", "      enabled: true"])
else:
    gateway_end = len(lines)
    for j in range(gateway_idx + 1, len(lines)):
        line = lines[j]
        if line and not line.startswith((" ", "#")):
            gateway_end = j
            break
    platforms_idx = None
    for j in range(gateway_idx + 1, gateway_end):
        if lines[j].strip() == "platforms:":
            platforms_idx = j
            break
    if platforms_idx is None:
        lines[gateway_idx + 1:gateway_idx + 1] = ["  platforms:", "    zalo:", "      enabled: true"]
    else:
        zalo_idx = None
        for j in range(platforms_idx + 1, gateway_end):
            if lines[j].strip() == "zalo:":
                zalo_idx = j
                break
            if lines[j].strip() and not lines[j].startswith("    "):
                break
        if zalo_idx is None:
            lines[platforms_idx + 1:platforms_idx + 1] = ["    zalo:", "      enabled: true"]
        else:
            zalo_end = gateway_end
            for j in range(zalo_idx + 1, gateway_end):
                if lines[j].strip() and not lines[j].startswith("      "):
                    zalo_end = j
                    break
            enabled_line = None
            for j in range(zalo_idx + 1, zalo_end):
                if lines[j].strip().startswith("enabled:"):
                    enabled_line = j
                    break
            if enabled_line is None:
                lines.insert(zalo_idx + 1, "      enabled: true")
            else:
                lines[enabled_line] = "      enabled: true"

cfg.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("OK: enabled zalo-platform")
PY
  zalo_log "enabled zalo-platform in ${cfg}"
}

ensure_hermes_model_router() {
  zalo_log "point Hermes shared config at model-router"
  STACK_ROOT="${ROOT}" \
    HERMES_DATA_DIR="${HERMES_SHARED_DATA}" \
    ASSISTANT_DATA_DIR="${HERMES_SHARED_DATA}" \
    python3 "${ROOT}/scripts/main/patch-hermes-model-router.py" || {
    echo "WARN: patch-hermes-model-router failed" >&2
  }
}

resolve_hermes_container() {
  local project="${COMPOSE_PROJECT_NAME:-assistant}"
  local name=""
  name="$(zalo_docker_cmd ps --format '{{.Names}}' 2>/dev/null | awk -v w="${project}-hermes-1" '$0==w {print; exit}')"
  if [[ -z "$name" ]]; then
    name="$(zalo_docker_cmd ps --format '{{.Names}}' 2>/dev/null | awk '/hermes/ {print; exit}')"
  fi
  printf '%s' "${name:-assistant-hermes-1}"
}

ensure_aiohttp_in_hermes() {
  local ctr="$1"
  local py_bin="/opt/hermes/.venv/bin/python"
  zalo_docker_cmd exec "$ctr" /bin/sh -lc "test -x '${py_bin}'" >/dev/null 2>&1 || py_bin="python3"
  if zalo_docker_cmd exec "$ctr" /bin/sh -lc "${py_bin} -c 'import aiohttp' >/dev/null 2>&1"; then
    return 0
  fi
  zalo_log "install aiohttp into ${ctr}"
  zalo_docker_cmd exec "$ctr" /bin/sh -lc "${py_bin} -m pip install --no-cache-dir aiohttp" || return 1
}

sync_replica_config_from_shared() {
  local ctr="$1"
  zalo_docker_cmd exec "$ctr" /bin/sh -lc '
    for f in /opt/data/replicas/*/config.yaml; do
      [ -f "$f" ] || continue
      cp -f /opt/data/config.yaml "$f" 2>/dev/null || true
      chmod 600 "$f" 2>/dev/null || true
    done
  ' || true
}

wire_env() {
  local local_env="${HERMES_SHARED_DATA}/.env"
  $ZALO_SUDO mkdir -p "$HERMES_SHARED_DATA"
  $ZALO_SUDO touch "$local_env"
  upsert_local() {
    local k="$1" v="$2"
    if $ZALO_SUDO grep -q "^${k}=" "$local_env"; then
      $ZALO_SUDO sed -i "s|^${k}=.*|${k}=${v}|" "$local_env"
    else
      echo "${k}=${v}" | $ZALO_SUDO tee -a "$local_env" >/dev/null
    fi
  }
  local bridge="http://host.docker.internal:${ZALO_PORT}"
  if [[ "${HERMES_REPLICAS:-1}" != "1" ]]; then
    bridge="http://zalo-proxy:${ZALO_PORT}"
  fi
  upsert_local ZALO_PLUGIN_URL "$bridge"
  upsert_local ZALO_BRIDGE_URL "$bridge"
  upsert_local ZALO_GROUP_MODE "${ZALO_GROUP_MODE:-mention}"
  upsert_local ZALO_HOST_DATA_DIR "$ZALO_HOST_DATA_DIR"
  upsert_local GATEWAY_ALLOW_ALL_USERS "${GATEWAY_ALLOW_ALL_USERS:-true}"
  zalo_env_upsert WORKER_MESSAGE active
  zalo_env_upsert ENABLE_ZALO 1
  zalo_env_upsert ZALO_PLUGIN_URL "$bridge"
  $ZALO_SUDO mkdir -p "${HERMES_SHARED_DATA}/channels" "${HERMES_SHARED_DATA}/media/inbound" "${HERMES_SHARED_DATA}/media/out"
  $ZALO_SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" \
    "$local_env" "${HERMES_SHARED_DATA}/media" 2>/dev/null || true
}

install_zalo_stack_after_qr() {
  local health_json="$1"
  zalo_log "QR OK — installing Zalo adapter, zalo-api, and Hermes plugin"
  install_adapter
  enable_plugin
  ensure_hermes_model_router
  wire_env

  cd "$ROOT"
  set -a && source ./.env && set +a
  export ENABLE_ZALO=1
  export WORKER_MESSAGE=active
  export ASSISTANT_UP_LIGHT=1

  if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S bash -lc \
      "cd ${ROOT} && set -a && . ./.env && set +a && export ENABLE_ZALO=1 WORKER_MESSAGE=active ASSISTANT_UP_LIGHT=1 && bash run.sh up" \
      || { zalo_log "ERROR: run.sh up failed"; return 1; }
  else
    ASSISTANT_UP_LIGHT=1 bash run.sh up || { zalo_log "ERROR: run.sh up failed"; return 1; }
  fi

  local hermes_ctr
  hermes_ctr="$(resolve_hermes_container)"
  ensure_aiohttp_in_hermes "$hermes_ctr"
  sync_replica_config_from_shared "$hermes_ctr"
  zalo_restart_all_services
  zalo_seed_admin "$health_json"
  zalo_backup_session

  cat <<EOF

────────────────────────────────────────────────────────────
Zalo setup complete (QR verified + stack running).

Bridge:  curl -fsS ${ZALO_HEALTH_URL}
zalo-api: curl -fsS http://127.0.0.1:${ZALO_API_PORT:-8100}/health

Admin: DM bot → !zalo claim  (then !zalo admin transfer @tag if needed)
Re-login only: bash scripts/main/login-zalo.sh
────────────────────────────────────────────────────────────
EOF
}

main() {
  zalo_ensure_deploy_user
  zalo_log "setup-zalo — QR first, then stack (cuongdev hermes-zalo-plugin)"
  zalo_log "preflight: fix ~/.config ownership for $(id -un) if needed"
  zalo_ensure_config_writable
  zalo_wait_core_for_qr || exit 1

  local health_json=""
  if health_json="$(zalo_qr_login_phase)"; then
    :
  else
    zalo_teardown_failed_qr
    echo "ERROR: setup-zalo aborted — scan QR and re-run: bash scripts/main/setup-zalo.sh" >&2
    exit 1
  fi

  install_zalo_stack_after_qr "$health_json"
}

main "$@"
