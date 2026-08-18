#!/usr/bin/env bash
# Install Zalo bridge + adapter AFTER profile services are ready.
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

HERMES_DATA="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
PLUGIN_SRC="${ROOT}/hermes/main/plugins/zalo"
PLUGIN_DIR="${HERMES_DATA}/plugins/zalo"
PORT="${ZALO_PLUGIN_PORT:-8787}"
HOST_BIND="${ZALO_PLUGIN_HOST:-0.0.0.0}"
ZALO_REPO_URL="${ZALO_REPO_URL:-https://github.com/cuongdev/hermes-zalo-plugin.git}"
PROFILE="${ASSISTANT_PROFILE:-low}"

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

wait_profile_ready() {
  log "wait for profile services (${PROFILE}) before installing Zalo plugin"
  case "$PROFILE" in
    high)
      bash "${ROOT}/scripts/main/check-medium.sh" || {
        echo "ERROR: Medium smoke failed — refuse Zalo install" >&2
        return 1
      }
      bash "${ROOT}/scripts/main/check-high.sh" || {
        echo "ERROR: High smoke failed — refuse Zalo install" >&2
        return 1
      }
      ;;
    medium)
      bash "${ROOT}/scripts/main/check-medium.sh" || return 1
      ;;
    *)
      local tries=60 i=0
      until curl -fsS -m 3 "http://127.0.0.1:${N9ROUTER_HOST_PORT:-20128}/v1/models" >/dev/null 2>&1; do
        i=$((i + 1))
        [[ "$i" -ge "$tries" ]] && {
          echo "ERROR: Low core not ready" >&2
          return 1
        }
        sleep 5
        echo "  waiting (${i}/${tries})…"
      done
      ;;
  esac
  log "profile services ready"
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
  $SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "${HERMES_DATA}/plugins" 2>/dev/null || true
}

enable_plugin() {
  local cfg="${HERMES_DATA}/config.yaml"
  if ! $SUDO test -f "$cfg"; then
    echo "WARN: missing ${cfg}" >&2
    return 0
  fi
  if $SUDO grep -qE '^\s*-\s*zalo-platform\s*$' "$cfg"; then
    log "zalo-platform already enabled"
    return 0
  fi
  if $SUDO grep -qE 'enabled:\s*\[\s*\]' "$cfg"; then
    $SUDO sed -i 's/enabled: \[\]/enabled:\n    - zalo-platform/' "$cfg"
  elif $SUDO grep -qE '^\s*enabled:' "$cfg"; then
    $SUDO sed -i '/^\s*enabled:/a\    - zalo-platform' "$cfg"
  else
    printf '\nplugins:\n  enabled:\n    - zalo-platform\n' | $SUDO tee -a "$cfg" >/dev/null
  fi
  log "enabled zalo-platform in ${cfg}"
}

wire_env() {
  local local_env="${HERMES_DATA}/.env"
  $SUDO mkdir -p "$HERMES_DATA"
  $SUDO touch "$local_env"
  upsert() {
    local k="$1" v="$2"
    if $SUDO grep -q "^${k}=" "$local_env"; then
      $SUDO sed -i "s|^${k}=.*|${k}=${v}|" "$local_env"
    else
      echo "${k}=${v}" | $SUDO tee -a "$local_env" >/dev/null
    fi
  }
  upsert ZALO_PLUGIN_URL "http://zalo-proxy:8787"
  upsert ZALO_BRIDGE_URL "http://zalo-proxy:8787"
  upsert ZALO_GROUP_MODE "${ZALO_GROUP_MODE:-mention}"
  upsert ZALO_HOST_DATA_DIR "$HERMES_DATA"
  upsert GATEWAY_ALLOW_ALL_USERS "${GATEWAY_ALLOW_ALL_USERS:-true}"
  $SUDO chmod 600 "$local_env" || true
  if [[ -f "${ROOT}/.env" ]]; then
    if grep -q '^ENABLE_ZALO=' "${ROOT}/.env"; then
      sed -i 's/^ENABLE_ZALO=.*/ENABLE_ZALO=1/' "${ROOT}/.env"
    else
      echo 'ENABLE_ZALO=1' >> "${ROOT}/.env"
    fi
    if grep -q '^ZALO_PLUGIN_URL=' "${ROOT}/.env"; then
      sed -i 's|^ZALO_PLUGIN_URL=.*|ZALO_PLUGIN_URL=http://zalo-proxy:8787|' "${ROOT}/.env"
    else
      echo 'ZALO_PLUGIN_URL=http://zalo-proxy:8787' >> "${ROOT}/.env"
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
  log "setup-zalo (install only) HERMES_DATA=${HERMES_DATA}"
  log "credit: Cường Tuấn Nguyễn / cuongdev — hermes-zalo-plugin (MIT)"
  wait_profile_ready
  install_bridge
  install_adapter
  enable_plugin
  wire_env
  cd "$ROOT"
  set -a && source ./.env && set +a
  export ENABLE_ZALO=1 ASSISTANT_PROFILE="${PROFILE}"
  if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S bash -lc \
      "cd ${ROOT} && set -a && . ./.env && set +a && export ENABLE_ZALO=1 ASSISTANT_PROFILE=${PROFILE} && bash run.sh up" || true
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S docker restart hermes zalo-proxy 2>/dev/null \
      || printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S docker restart hermes || true
  else
    $SUDO bash -lc "cd ${ROOT} && set -a && . ./.env && set +a && export ENABLE_ZALO=1 ASSISTANT_PROFILE=${PROFILE} && bash run.sh up" || true
    $SUDO docker restart hermes zalo-proxy 2>/dev/null || $SUDO docker restart hermes || true
  fi
  print_next
}

main "$@"
