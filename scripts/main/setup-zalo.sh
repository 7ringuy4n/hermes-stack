#!/usr/bin/env bash
# Install Zalo bridge + adapter AFTER worker services are ready.
# Does NOT perform QR login — that is a manual last step:
#   bash scripts/main/login-zalo.sh
#
# Upstream: hermes-zalo-plugin by Cường Tuấn Nguyễn (cuongdev) — MIT
#   https://github.com/cuongdev/hermes-zalo-plugin
#
# Usage:
#   ENABLE_ZALO=1 bash scripts/main/setup-zalo.sh
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a

# Host path mounted into Hermes as /opt/data (see docker-compose hermes volumes).
# Do NOT use bare host /opt/data — that is a different directory from ASSISTANT_DATA_DIR.
ZALO_HOST_DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
HERMES_SHARED_DATA="${HERMES_SHARED_DATA_DIR:-${ASSISTANT_DATA_DIR:-${HERMES_DATA_DIR:-/data/assistant}}}"
PLUGIN_SRC="${ROOT}/hermes/main/plugins/zalo"
PLUGIN_DIR="${HERMES_SHARED_DATA}/plugins/zalo"
PORT="${ZALO_PLUGIN_PORT:-8787}"
HOST_BIND="${ZALO_PLUGIN_HOST:-0.0.0.0}"
ZALO_REPO_URL="${ZALO_REPO_URL:-https://github.com/cuongdev/hermes-zalo-plugin.git}"
if [[ "$(id -u)" -ne 0 ]]; then SUDO=sudo; else SUDO=; fi

# Non-interactive deploy (paramiko): cache sudo creds so later $SUDO calls do not hang on a TTY prompt.
if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" && "$(id -u)" -ne 0 ]]; then
  if ! printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S -v >/dev/null 2>&1; then
    echo "ERROR: ASSISTANT_SUDO_PASSWORD rejected by sudo" >&2
    exit 1
  fi
fi

log() { echo "==> $*"; }

ensure_user_bus() {
  # sudo -u / paramiko has no login session; linger + XDG_RUNTIME_DIR are required
  # for systemctl --user (otherwise: Failed to connect to bus: No medium found).
  if [[ "$(id -u)" -eq 0 ]]; then
    return 0
  fi
  local uid
  uid="$(id -u)"
  $SUDO loginctl enable-linger "${USER}" 2>/dev/null || true
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${uid}}"
  local i
  for i in $(seq 1 25); do
    if [[ -S "${XDG_RUNTIME_DIR}/bus" ]]; then
      export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"
      return 0
    fi
    sleep 1
  done
  log "WARN: user systemd bus not ready (${XDG_RUNTIME_DIR}/bus)"
  return 1
}

wait_core_ready() {
  # Worker model: wait for Router Worker / OmniRouter (default) and Message Worker zalo-api.
  # Do not wait on 9Router (optional) or obsolete ASSISTANT_PROFILE tiers.
  log "wait for core services before installing Zalo plugin"
  local tries=60 i=0
  local router_ok=0 omni_ok=0 zalo_api_ok=0
  local model_port="${MODEL_ROUTER_PORT:-8096}"
  local omni_port="${OMNIROUTER_HOST_PORT:-20129}"
  local zalo_api_port="${ZALO_API_PORT:-${ADMIN_API_PORT:-8100}}"

  for i in $(seq 1 "$tries"); do
    router_ok=0
    omni_ok=0
    zalo_api_ok=0
    curl -fsS -m 3 "http://127.0.0.1:${model_port}/health" >/dev/null 2>&1 && router_ok=1
    if [[ "${ENABLE_OMNIROUTER:-1}" == "1" ]]; then
      if curl -fsS -m 3 "http://127.0.0.1:${omni_port}/" >/dev/null 2>&1 \
        || curl -fsS -m 3 "http://127.0.0.1:${omni_port}/v1/models" >/dev/null 2>&1; then
        omni_ok=1
      fi
    else
      omni_ok=1
    fi
    curl -fsS -m 3 "http://127.0.0.1:${zalo_api_port}/health" >/dev/null 2>&1 && zalo_api_ok=1
    if [[ "$router_ok" == "1" && "$omni_ok" == "1" && "$zalo_api_ok" == "1" ]]; then
      log "core services ready (model-router + omni + zalo-api)"
      return 0
    fi
    sleep 5
    echo "  waiting (${i}/${tries}) router=${router_ok} omni=${omni_ok} zalo-api=${zalo_api_ok}…"
  done
  echo "ERROR: core not ready for Zalo (need model-router, OmniRouter when enabled, and zalo-api)" >&2
  return 1
}

need_node() {
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    return 0
  fi
  log "install Node.js 20 (nodesource)"
  # Avoid `curl | sudo bash` hanging on a TTY password prompt under paramiko.
  local setup_tmp
  setup_tmp="$(mktemp)"
  curl -fsSL https://deb.nodesource.com/setup_20.x -o "$setup_tmp"
  if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S bash "$setup_tmp"
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S apt-get install -y nodejs
  else
    $SUDO bash "$setup_tmp"
    $SUDO apt-get install -y nodejs
  fi
  rm -f "$setup_tmp"
}

install_bridge() {
  # Package install + systemd only — NO QR login here
  need_node
  if ! command -v hermes-zalo-plugin >/dev/null 2>&1; then
    log "npm install -g hermes-zalo-plugin (upstream: cuongdev / Cường Tuấn Nguyễn)"
    if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" ]]; then
      printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S npm install -g hermes-zalo-plugin || {
        log "npmjs failed — clone + install from git"
        local tmp
        tmp="$(mktemp -d)"
        git clone --depth 1 "$ZALO_REPO_URL" "${tmp}/p"
        (cd "${tmp}/p" && printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S npm install -g .)
        rm -rf "$tmp"
      }
    else
      $SUDO npm install -g hermes-zalo-plugin || {
        log "npmjs failed — clone + install from git"
        local tmp
        tmp="$(mktemp -d)"
        git clone --depth 1 "$ZALO_REPO_URL" "${tmp}/p"
        (cd "${tmp}/p" && $SUDO npm install -g .)
        rm -rf "$tmp"
      }
    fi
  fi

  log "bridge service-only setup (login is manual: bash scripts/main/login-zalo.sh)"
  hermes-zalo-plugin setup --service-only 2>/dev/null || true

  local drop="${HOME}/.config/systemd/user/com.hermes.zaloplugin.service.d"
  mkdir -p "$drop"
  cat > "${drop}/override.conf" <<EOF
[Service]
Environment=ZALO_PLUGIN_HOST=${HOST_BIND}
Environment=ZALO_PLUGIN_PORT=${PORT}
Environment=ZALO_DISPATCHER_URL=http://127.0.0.1:8090
Environment=ZALO_API_URL=http://127.0.0.1:${ZALO_API_PORT:-${ADMIN_API_PORT:-8100}}
Environment=ZALO_API_TOKEN=${ZALO_API_TOKEN:-${ADMIN_API_TOKEN:-}}
Environment=ADMIN_API_URL=http://127.0.0.1:${ZALO_API_PORT:-${ADMIN_API_PORT:-8100}}
Environment=ADMIN_API_TOKEN=${ZALO_API_TOKEN:-${ADMIN_API_TOKEN:-}}
EOF

  local bin
  bin="$(command -v hermes-zalo-plugin)"
  mkdir -p "${HOME}/.config/systemd/user"
  ensure_user_bus || true
  if ! systemctl --user list-unit-files 2>/dev/null | grep -q '^com.hermes.zaloplugin.service'; then
    cat > "${HOME}/.config/systemd/user/assistant-zalo.service" <<EOF
[Unit]
Description=assistant Zalo bridge (upstream: hermes-zalo-plugin by Cường Tuấn Nguyễn)
After=network.target

[Service]
Type=simple
Environment=ZALO_PLUGIN_HOST=${HOST_BIND}
Environment=ZALO_PLUGIN_PORT=${PORT}
ExecStart=${bin} start
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
  fi
  systemctl --user daemon-reload 2>/dev/null || true
  if systemctl --user list-unit-files 2>/dev/null | grep -q '^com.hermes.zaloplugin.service'; then
    systemctl --user enable --now com.hermes.zaloplugin.service 2>/dev/null || true
  else
    systemctl --user enable --now assistant-zalo.service 2>/dev/null || true
  fi
  if ! curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    log "user systemd did not start bridge — launching hermes-zalo-plugin start"
    nohup "$bin" start >/tmp/hermes-zalo-plugin.log 2>&1 &
    sleep 2
  fi
  loginctl enable-linger "${USER}" 2>/dev/null || true
  if command -v ufw >/dev/null 2>&1; then
    $SUDO ufw allow from 172.16.0.0/12 to any port "$PORT" proto tcp comment 'docker->zalo' || true
  fi
}

install_adapter() {
  $SUDO mkdir -p "$(dirname "$PLUGIN_DIR")"
  if [[ -d "$PLUGIN_SRC" ]]; then
    log "copy adapter ${PLUGIN_SRC} → ${PLUGIN_DIR}"
    $SUDO rm -rf "$PLUGIN_DIR"
    $SUDO cp -a "$PLUGIN_SRC" "$PLUGIN_DIR"
  else
    echo "WARN: missing ${PLUGIN_SRC}" >&2
    return 1
  fi
  $SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "${HERMES_SHARED_DATA}/plugins" 2>/dev/null || true
}

ensure_shared_config() {
  local cfg="${HERMES_SHARED_DATA}/config.yaml"
  if $SUDO test -f "$cfg"; then
    return 0
  fi

  local seed
  seed="$($SUDO bash -lc "ls -1dt '${HERMES_SHARED_DATA}'/replicas/*/config.yaml 2>/dev/null | head -n 1" || true)"
  if [[ -z "$seed" ]]; then
    log "WARN: missing ${cfg} (and no replica config.yaml found under ${HERMES_SHARED_DATA}/replicas) — creating minimal config"
    $SUDO tee "$cfg" >/dev/null <<'EOF'
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
    log "seed shared config.yaml from ${seed}"
    $SUDO cp -a "$seed" "$cfg"
  fi
  $SUDO chown "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "$cfg" 2>/dev/null || true
  $SUDO chmod 600 "$cfg" 2>/dev/null || true
}

enable_plugin() {
  local cfg="${HERMES_SHARED_DATA}/config.yaml"
  ensure_shared_config
  $SUDO python3 - "$cfg" <<'PY'
from pathlib import Path
import sys

cfg = Path(sys.argv[1])
lines = cfg.read_text(encoding="utf-8", errors="replace").splitlines()
# Remove any stray/misplaced prior insertions before re-adding correctly.
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

# Ensure gateway.platforms.zalo is enabled on clean hosts.
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
            stripped = lines[j].strip()
            if stripped == "zalo:":
                zalo_idx = j
                break
            if stripped and not lines[j].startswith("    "):
                break

        if zalo_idx is None:
            lines[platforms_idx + 1:platforms_idx + 1] = ["    zalo:", "      enabled: true"]
        else:
            zalo_end = gateway_end
            for j in range(zalo_idx + 1, gateway_end):
                line = lines[j]
                if line.strip() and not line.startswith("      "):
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
  log "enabled zalo-platform in ${cfg}"
}

ensure_hermes_model_router() {
  log "point Hermes shared config at model-router (OmniRouter default)"
  local stack_env="${ROOT}/.env"
  STACK_ROOT="${ROOT}" \
    HERMES_DATA_DIR="${HERMES_SHARED_DATA}" \
    ASSISTANT_DATA_DIR="${HERMES_SHARED_DATA}" \
    python3 "${ROOT}/scripts/main/patch-hermes-model-router.py" || {
    echo "WARN: patch-hermes-model-router failed — Hermes may still use openrouter.ai" >&2
  }
}

resolve_hermes_container() {
  local project="${COMPOSE_PROJECT_NAME:-assistant}"
  local exact="${HERMES_CONTAINER:-hermes}"
  local name=""
  name="$($SUDO docker ps --format '{{.Names}}' 2>/dev/null | awk -v w="$exact" '$0==w {print; exit}')"
  if [[ -z "$name" ]]; then
    name="$($SUDO docker ps --format '{{.Names}}' 2>/dev/null | awk -v w="${project}-hermes-1" '$0==w {print; exit}')"
  fi
  if [[ -z "$name" ]]; then
    name="$($SUDO docker ps --format '{{.Names}}' 2>/dev/null | awk '/hermes/ {print; exit}')"
  fi
  printf '%s' "${name:-$exact}"
}

ensure_aiohttp_in_hermes() {
  local ctr="$1"
  # Hermes gateway runs inside /opt/hermes/.venv; use that interpreter if present.
  local py_bin="/opt/hermes/.venv/bin/python"
  $SUDO docker exec "$ctr" /bin/sh -lc "test -x '${py_bin}'" >/dev/null 2>&1 || py_bin="python3"

  if $SUDO docker exec "$ctr" /bin/sh -lc "${py_bin} -c 'import aiohttp' >/dev/null 2>&1"; then
    log "aiohttp already present in ${ctr}"
    return 0
  fi
  log "install aiohttp into ${ctr} (required for zalo-platform SSE)"
  $SUDO docker exec "$ctr" /bin/sh -lc "${py_bin} -m pip --version" >/dev/null 2>&1 || \
    $SUDO docker exec "$ctr" /bin/sh -lc "${py_bin} -m ensurepip --upgrade" >/dev/null 2>&1 || true

  $SUDO docker exec "$ctr" /bin/sh -lc "${py_bin} -m pip install --no-cache-dir aiohttp" || {
    echo "ERROR: failed to install aiohttp in ${ctr}" >&2
    return 1
  }
  return 0
}

sync_replica_config_from_shared() {
  local ctr="$1"
  log "sync replica config.yaml from /opt/data/config.yaml in ${ctr}"
  $SUDO docker exec "$ctr" /bin/sh -lc '
    for f in /opt/data/replicas/*/config.yaml; do
      [ -f "$f" ] || continue
      cp -f /opt/data/config.yaml "$f" 2>/dev/null || true
      chmod 600 "$f" 2>/dev/null || true
    done
  ' || true
}

wire_env() {
  local local_env="${HERMES_SHARED_DATA}/.env"
  $SUDO mkdir -p "$HERMES_SHARED_DATA"
  $SUDO touch "$local_env"
  upsert() {
    local k="$1" v="$2"
    if $SUDO grep -q "^${k}=" "$local_env"; then
      $SUDO sed -i "s|^${k}=.*|${k}=${v}|" "$local_env"
    else
      echo "${k}=${v}" | $SUDO tee -a "$local_env" >/dev/null
    fi
  }
  local bridge="http://host.docker.internal:8787"
  if [[ "${HERMES_REPLICAS:-1}" != "1" ]]; then
    bridge="http://zalo-proxy:8787"
  fi
  upsert ZALO_PLUGIN_URL "$bridge"
  upsert ZALO_BRIDGE_URL "$bridge"
  upsert ZALO_GROUP_MODE "${ZALO_GROUP_MODE:-mention}"
  upsert ZALO_HOST_DATA_DIR "$ZALO_HOST_DATA_DIR"
  upsert GATEWAY_ALLOW_ALL_USERS "${GATEWAY_ALLOW_ALL_USERS:-true}"
  $SUDO mkdir -p "${HERMES_SHARED_DATA}/channels"
  $SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" \
    "$local_env" \
    "${HERMES_SHARED_DATA}/config.yaml" \
    "${HERMES_SHARED_DATA}/channels" \
    "${HERMES_SHARED_DATA}/zalo_admin_users.txt" \
    "${HERMES_SHARED_DATA}/zalo_allowed_threads.txt" \
    2>/dev/null || true
  $SUDO chmod 600 "$local_env" || true
  # Hermes may rewrite shared .env / config.yaml — keep the parent writable by HERMES_UID.
  $SUDO chmod u+w "$HERMES_SHARED_DATA" 2>/dev/null || true
  if [[ -f "${ROOT}/.env" ]]; then
    if grep -q '^ENABLE_ZALO=' "${ROOT}/.env"; then
      sed -i 's/^ENABLE_ZALO=.*/ENABLE_ZALO=1/' "${ROOT}/.env"
    else
      echo 'ENABLE_ZALO=1' >> "${ROOT}/.env"
    fi
    if grep -q '^ZALO_PLUGIN_URL=' "${ROOT}/.env"; then
      sed -i "s|^ZALO_PLUGIN_URL=.*|ZALO_PLUGIN_URL=${bridge}|" "${ROOT}/.env"
    else
      echo "ZALO_PLUGIN_URL=${bridge}" >> "${ROOT}/.env"
    fi
  fi
}

print_next() {
  cat <<EOF

────────────────────────────────────────────────────────────
Zalo install complete (no login yet).

Upstream bridge: hermes-zalo-plugin
Author: Cường Tuấn Nguyễn (cuongdev) — MIT
https://github.com/cuongdev/hermes-zalo-plugin

MANUAL LAST STEP (required):
  bash scripts/main/login-zalo.sh

  Then tunnel if remote:
    ssh -L 8787:127.0.0.1:8787 USER@HOST
  QR: http://127.0.0.1:8787/qr.png

Admin (exactly one user):
  login-zalo seeds admin = Zalo proxy ownId (account that scanned QR)
  Then DM bot from your personal Zalo:
    !zalo claim
    !zalo admin transfer @tag|uid|reply

Self-heal (silent):
  systemd timers assistant-stack-watch (2m) + assistant-zalo-watch (1m when ENABLE_ZALO=1)
  Adapter drops poison Last-Event-ID if SSE reconnect loops
────────────────────────────────────────────────────────────
EOF
}

main() {
  log "setup-zalo (install only) ZALO_HOST_DATA_DIR=${ZALO_HOST_DATA_DIR} HERMES_SHARED_DATA=${HERMES_SHARED_DATA}"
  log "credit: Cường Tuấn Nguyễn / cuongdev — hermes-zalo-plugin (MIT)"
  wait_core_ready
  install_bridge
  install_adapter
  enable_plugin
  ensure_hermes_model_router
  wire_env
  cd "$ROOT"
  set -a && source ./.env && set +a
  export ENABLE_ZALO=1
  local hermes_ctr
  hermes_ctr="$(resolve_hermes_container)"
  if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S bash -lc \
      "cd ${ROOT} && set -a && . ./.env && set +a && export ENABLE_ZALO=1 && bash run.sh up" || true
  else
    $SUDO bash -lc "cd ${ROOT} && set -a && . ./.env && set +a && export ENABLE_ZALO=1 && bash run.sh up" || true
  fi

  # run.sh up may recreate containers; re-resolve and ensure Python deps after it.
  hermes_ctr="$(resolve_hermes_container)"
  ensure_aiohttp_in_hermes "$hermes_ctr"
  sync_replica_config_from_shared "$hermes_ctr"

  if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S docker restart "$hermes_ctr" zalo-proxy 2>/dev/null \
      || printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S docker restart "$hermes_ctr" || true
  else
    $SUDO docker restart "$hermes_ctr" zalo-proxy 2>/dev/null || $SUDO docker restart "$hermes_ctr" || true
  fi
  print_next
}

main "$@"
