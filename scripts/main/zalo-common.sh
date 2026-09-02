#!/usr/bin/env bash
# Shared Zalo bridge helpers — sourced by setup-zalo.sh and login-zalo.sh.
# QR login must succeed before docker zalo-api / full bridge stack install.
set -euo pipefail

_zalo_common_loaded="${_zalo_common_loaded:-0}"
[[ "$_zalo_common_loaded" == "1" ]] && return 0
_zalo_common_loaded=1

ZALO_COMMON_ROOT="${ZALO_COMMON_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ZALO_COMMON_ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ZALO_COMMON_ROOT}/.env") && set +a

ZALO_HOST_DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
HERMES_SHARED_DATA="${HERMES_SHARED_DATA_DIR:-${ASSISTANT_DATA_DIR:-${HERMES_DATA_DIR:-/data/assistant}}}"
ZALO_PORT="${ZALO_PLUGIN_PORT:-8787}"
ZALO_HOST_BIND="${ZALO_PLUGIN_HOST:-0.0.0.0}"
ZALO_HEALTH_URL="http://127.0.0.1:${ZALO_PORT}/health"
ZALO_QR_URL="http://127.0.0.1:${ZALO_PORT}/qr.png"
ZALO_REPO_URL="${ZALO_REPO_URL:-https://github.com/cuongdev/hermes-zalo-plugin.git}"
ZALO_LOGIN_WAIT_S="${ZALO_LOGIN_HEALTH_WAIT_S:-300}"
ZALO_ADMIN_FILE="${ZALO_ADMIN_USERS_FILE:-${ZALO_HOST_DATA_DIR}/zalo_admin_users.txt}"

if [[ "$(id -u)" -ne 0 ]]; then ZALO_SUDO=sudo; else ZALO_SUDO=; fi

zalo_log() { echo "==> $*"; }

zalo_docker_cmd() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  elif [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" && "$(id -u)" -ne 0 ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S docker "$@"
  else
    $ZALO_SUDO docker "$@"
  fi
}

zalo_ensure_deploy_user() {
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "ERROR: run as deploy user (not root)." >&2
    echo "  Example: bash scripts/main/setup-zalo.sh" >&2
    exit 1
  fi
}

zalo_ensure_config_writable() {
  # Bridge systemd units live under ~/.config/systemd/user — must belong to deploy user
  # (not root). Wrong owner → EACCES, bridge down, Hermes connection refused on :8787.
  local cfg="${HOME}/.config"
  local user group
  user="$(id -un)"
  group="$(id -gn)"
  mkdir -p "${cfg}/systemd/user" 2>/dev/null || true
  local need_fix=0
  if [[ ! -w "${cfg}/systemd/user" ]] 2>/dev/null; then
    need_fix=1
  elif [[ -d "${cfg}/systemd/user" ]] \
    && find "${cfg}/systemd/user" -maxdepth 3 ! -user "$user" 2>/dev/null | grep -q .; then
    need_fix=1
  elif ! touch "${cfg}/systemd/user/.write_test" 2>/dev/null; then
    need_fix=1
  fi
  if [[ "$need_fix" == "1" ]]; then
    zalo_log "fix ~/.config ownership for ${user}: sudo chown -R ${user}:${group} ${cfg}"
    $ZALO_SUDO chown -R "${user}:${group}" "$cfg"
  fi
  rm -f "${cfg}/systemd/user/.write_test" 2>/dev/null || true
}

zalo_heal_sse() {
  local script="${ZALO_COMMON_ROOT}/scripts/main/heal-zalo-sse.sh"
  if [[ -f "$script" ]]; then
    zalo_log "heal Hermes↔bridge SSE (${script} — re-run anytime later)"
    bash "$script" || true
    return 0
  fi
  local hermes_ctr
  hermes_ctr="$(zalo_docker_cmd ps --format '{{.Names}}' 2>/dev/null | awk '/hermes/ {print; exit}')"
  zalo_log "WARN: heal-zalo-sse.sh missing — fallback restart zalo-api + Hermes"
  zalo_docker_cmd restart zalo-api 2>/dev/null || true
  [[ -n "$hermes_ctr" ]] && zalo_docker_cmd restart "$hermes_ctr" zalo-proxy 2>/dev/null \
    || [[ -n "$hermes_ctr" ]] && zalo_docker_cmd restart "$hermes_ctr" 2>/dev/null || true
  sleep 8
}

zalo_ensure_user_bus() {
  if [[ "$(id -u)" -eq 0 ]]; then
    return 0
  fi
  local uid
  uid="$(id -u)"
  $ZALO_SUDO loginctl enable-linger "${USER}" 2>/dev/null || true
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${uid}}"
  local i
  for i in $(seq 1 25); do
    if [[ -S "${XDG_RUNTIME_DIR}/bus" ]]; then
      export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"
      return 0
    fi
    sleep 1
  done
  zalo_log "WARN: user systemd bus not ready (${XDG_RUNTIME_DIR}/bus)"
  return 1
}

zalo_bridge_health_ready() {
  python3 -c '
import json, sys
raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(1)
try:
    d = json.loads(raw)
except Exception:
    raise SystemExit(1)
if d.get("sessionDead") is True:
    raise SystemExit(1)
own = str(d.get("ownId") or "").strip()
if d.get("loggedIn") is True and own:
    raise SystemExit(0)
if own and d.get("qr") in (None, "", "null"):
    raise SystemExit(0)
raise SystemExit(1)
'
}

zalo_bridge_logged_in_now() {
  local raw
  raw="$(curl -sf -m 5 "$ZALO_HEALTH_URL" 2>/dev/null || true)"
  [[ -n "$raw" ]] && printf '%s' "$raw" | zalo_bridge_health_ready
}

zalo_wait_bridge_logged_in() {
  local raw="" i max="${ZALO_LOGIN_WAIT_S}"
  zalo_log "wait for bridge loggedIn + ownId (up to ${max}s)"
  sleep 2
  for ((i = 1; i <= max; i++)); do
    raw="$(curl -sf -m 5 "$ZALO_HEALTH_URL" 2>/dev/null || true)"
    if [[ -n "$raw" ]] && printf '%s' "$raw" | zalo_bridge_health_ready; then
      zalo_log "bridge logged in (${i}s)"
      printf '%s' "$raw"
      return 0
    fi
    if [[ "$i" -eq 1 || $((i % 20)) -eq 0 ]]; then
      local state="unreachable"
      if [[ -n "$raw" ]]; then
        state="$(printf '%s' "$raw" | python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read())
except Exception:
    print("invalid_json"); raise SystemExit(0)
parts = []
if d.get("loggedIn") is True:
    parts.append("loggedIn")
elif d.get("qr"):
    parts.append("qr")
else:
    parts.append("loggedOut")
if d.get("ownId"):
    parts.append("ownId")
print(",".join(parts) or "unknown")
' 2>/dev/null || echo "invalid_json")"
      fi
      zalo_log "  … waiting scan (${i}/${max}s, state=${state})"
    fi
    sleep 1
  done
  zalo_log "ERROR: QR login timed out — bridge not logged in"
  printf '%s' "$raw"
  return 1
}

zalo_wait_bridge_port() {
  local i
  for i in $(seq 1 30); do
    if curl -sf -m 3 "$ZALO_HEALTH_URL" >/dev/null 2>&1 \
      || curl -sf -m 3 -o /dev/null -w '' "$ZALO_QR_URL" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# Non-interactive apt/sudo for headless VPS (avoids debconf/readline hangs on setup-zalo).
zalo_sudo_hint() {
  if [[ -z "${ASSISTANT_SUDO_PASSWORD:-}" ]] && [[ "$(id -u)" -ne 0 ]]; then
    zalo_log "sudo password required next (typing is hidden) — or set ASSISTANT_SUDO_PASSWORD in .env"
  fi
}

zalo_sudo_run() {
  local env_prefix="DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a"
  if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S -E env $env_prefix "$@"
  else
    zalo_sudo_hint
    $ZALO_SUDO env $env_prefix "$@"
  fi
}

zalo_wait_apt_lock() {
  local i
  for i in $(seq 1 90); do
    if ! $ZALO_SUDO fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
      && ! $ZALO_SUDO fuser /var/lib/apt/lists/lock >/dev/null 2>&1; then
      return 0
    fi
    if [[ "$i" -eq 1 || $((i % 15)) -eq 0 ]]; then
      zalo_log "waiting for apt lock (${i}/90)…"
    fi
    sleep 2
  done
  echo "ERROR: apt lock still held — stop other apt/dpkg jobs and retry" >&2
  return 1
}

zalo_node_major() {
  node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1
}

zalo_need_node() {
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    local major
    major="$(zalo_node_major)"
    if [[ -n "$major" && "$major" -ge 18 ]]; then
      zalo_log "Node.js $(node -v) npm $(npm -v)"
      return 0
    fi
    zalo_log "WARN: Node.js $(node -v) is too old — installing Node 20"
  fi

  zalo_log "Node.js not found — installing Node 20 (needs sudo)"
  if ! command -v curl >/dev/null 2>&1; then
    zalo_log "install curl (required for Node.js repo)"
    zalo_wait_apt_lock || return 1
    zalo_sudo_run apt-get -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
      install -y curl ca-certificates gnupg || return 1
  fi

  zalo_log "install Node.js 20 (nodesource apt repo) — may take a few minutes on first setup"
  zalo_wait_apt_lock || return 1

  # Add repo directly (do not run nodesource setup_20.x — it spawns nested apt jobs that can
  # hang on headless VPS when debconf/readline waits on a background TTY).
  zalo_sudo_run bash -c '
set -euo pipefail
apt-get -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
  install -y ca-certificates curl gnupg
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
  | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
chmod 0644 /etc/apt/keyrings/nodesource.gpg
cat > /etc/apt/sources.list.d/nodesource.list <<EOF
deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main
EOF
apt-get update -qq
apt-get -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold install -y nodejs
' || {
    echo "ERROR: Node.js install failed" >&2
    echo "  Manual fix:" >&2
    echo "    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -" >&2
    echo "    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs" >&2
    return 1
  }

  hash -r 2>/dev/null || true
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: node/npm not on PATH after install" >&2
    return 1
  fi
  zalo_log "Node.js $(node -v) npm $(npm -v)"
}

zalo_install_plugin_package() {
  if command -v hermes-zalo-plugin >/dev/null 2>&1; then
    zalo_install_bridge_overlays || true
    return 0
  fi
  zalo_log "npm install -g hermes-zalo-plugin (upstream: cuongdev)"
  if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S env DEBIAN_FRONTEND=noninteractive npm install -g hermes-zalo-plugin || {
      local tmp
      tmp="$(mktemp -d)"
      git clone --depth 1 "$ZALO_REPO_URL" "${tmp}/p"
      (cd "${tmp}/p" && printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S npm install -g .)
      rm -rf "$tmp"
    }
  else
    zalo_sudo_hint
    $ZALO_SUDO env DEBIAN_FRONTEND=noninteractive npm install -g hermes-zalo-plugin || {
      local tmp
      tmp="$(mktemp -d)"
      git clone --depth 1 "$ZALO_REPO_URL" "${tmp}/p"
      (cd "${tmp}/p" && $ZALO_SUDO npm install -g .)
      rm -rf "$tmp"
    }
  fi
  zalo_install_bridge_overlays || true
}

zalo_bridge_plugin_dir() {
  local bin dir npm_root
  bin="$(command -v hermes-zalo-plugin 2>/dev/null || true)"
  if [[ -n "$bin" ]]; then
    dir="$(readlink -f "$bin" 2>/dev/null || true)"
    if [[ -n "$dir" ]]; then
      dir="$(dirname "$dir")"
      if [[ -f "${dir}/zaloClient.js" ]]; then
        printf '%s' "$dir"
        return 0
      fi
    fi
  fi
  npm_root="$(npm root -g 2>/dev/null || true)"
  if [[ -n "$npm_root" && -f "${npm_root}/hermes-zalo-plugin/zaloClient.js" ]]; then
    printf '%s/hermes-zalo-plugin' "$npm_root"
    return 0
  fi
  if [[ -f "/usr/lib/node_modules/hermes-zalo-plugin/zaloClient.js" ]]; then
    printf '/usr/lib/node_modules/hermes-zalo-plugin'
    return 0
  fi
  return 1
}

zalo_bridge_overlay_files() {
  # Keep in sync with scripts/main/zalo-bridge/ — zaloClient.js imports ./markdownToZalo.js
  # but npm hermes-zalo-plugin@1.0.x does not ship it; overlay bundle must include deps.
  printf '%s\n' zaloClient.js markdownToZalo.js
}

zalo_bridge_overlay_cp() {
  local src="$1" dest="$2"
  if [[ -n "${ASSISTANT_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "$ASSISTANT_SUDO_PASSWORD" | sudo -S cp -f "$src" "$dest"
  else
    $ZALO_SUDO cp -f "$src" "$dest"
  fi
}

zalo_verify_bridge_overlays() {
  local dest_dir="$1"
  local f missing=0
  zalo_need_node
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    if ! node --check "${dest_dir}/${f}" 2>/dev/null; then
      zalo_log "ERROR: bridge overlay failed node --check: ${dest_dir}/${f}"
      return 1
    fi
  done < <(zalo_bridge_overlay_files)
  if ! python3 - "$dest_dir" <<'PY'
import re, sys
from pathlib import Path

dest = Path(sys.argv[1])
client = dest / "zaloClient.js"
text = client.read_text(encoding="utf-8")
missing = []
for m in re.finditer(r'from\s+"\./([^"]+)"', text):
    rel = m.group(1)
    if not (dest / rel).is_file():
        missing.append(rel)
if missing:
    for rel in missing:
        print(f"missing local import ./{rel}", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    zalo_log "ERROR: bridge overlay missing local imports (see above)"
    return 1
  fi
  zalo_log "bridge overlay verified (syntax + local imports)"
}

zalo_install_bridge_overlays() {
  local overlay_dir="${ZALO_COMMON_ROOT}/scripts/main/zalo-bridge"
  local dest_dir dest f src
  if [[ ! -d "$overlay_dir" ]]; then
    zalo_log "WARN: missing bridge overlay dir ${overlay_dir}"
    return 1
  fi
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    if [[ ! -f "${overlay_dir}/${f}" ]]; then
      zalo_log "WARN: missing bridge overlay ${overlay_dir}/${f}"
      return 1
    fi
  done < <(zalo_bridge_overlay_files)
  dest_dir="$(zalo_bridge_plugin_dir)" || {
    zalo_log "WARN: hermes-zalo-plugin install dir not found — skip bridge overlay"
    return 1
  }
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    src="${overlay_dir}/${f}"
    dest="${dest_dir}/${f}"
    zalo_log "install bridge overlay ${src} → ${dest}"
    zalo_bridge_overlay_cp "$src" "$dest"
  done < <(zalo_bridge_overlay_files)
  zalo_verify_bridge_overlays "$dest_dir"
}

zalo_configure_bridge_systemd() {
  local api_port="${ZALO_API_PORT:-${ADMIN_API_PORT:-8100}}"
  zalo_install_plugin_package
  hermes-zalo-plugin setup --service-only 2>/dev/null || true

  local drop="${HOME}/.config/systemd/user/com.hermes.zaloplugin.service.d"
  mkdir -p "$drop"
  cat > "${drop}/override.conf" <<EOF
[Service]
Environment=ZALO_PLUGIN_HOST=${ZALO_HOST_BIND}
Environment=ZALO_PLUGIN_PORT=${ZALO_PORT}
Environment=ZALO_DISPATCHER_URL=http://127.0.0.1:8090
Environment=ZALO_API_URL=http://127.0.0.1:${api_port}
Environment=ZALO_API_TOKEN=${ZALO_API_TOKEN:-${ADMIN_API_TOKEN:-}}
Environment=ZALO_PLUGIN_TOKEN=${ZALO_PLUGIN_TOKEN:-}
Environment=ADMIN_API_URL=http://127.0.0.1:${api_port}
Environment=ADMIN_API_TOKEN=${ZALO_API_TOKEN:-${ADMIN_API_TOKEN:-}}
EOF

  local bin
  bin="$(command -v hermes-zalo-plugin)"
  mkdir -p "${HOME}/.config/systemd/user"
  if ! systemctl --user list-unit-files 2>/dev/null | grep -q '^com.hermes.zaloplugin.service'; then
    cat > "${HOME}/.config/systemd/user/assistant-zalo.service" <<EOF
[Unit]
Description=assistant Zalo bridge (upstream: hermes-zalo-plugin by Cường Tuấn Nguyễn)
After=network.target

[Service]
Type=simple
Environment=ZALO_PLUGIN_HOST=${ZALO_HOST_BIND}
Environment=ZALO_PLUGIN_PORT=${ZALO_PORT}
ExecStart=${bin} start
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
  fi
  zalo_ensure_user_bus || true
  systemctl --user daemon-reload 2>/dev/null || true
}

zalo_start_bridge_service() {
  if systemctl --user list-unit-files 2>/dev/null | grep -q '^com.hermes.zaloplugin.service'; then
    systemctl --user enable --now com.hermes.zaloplugin.service 2>/dev/null || true
  else
    systemctl --user enable --now assistant-zalo.service 2>/dev/null || true
  fi
  if ! zalo_install_bridge_overlays; then
    zalo_log "ERROR: bridge overlay install/verify failed — fix before starting bridge"
    return 1
  fi
  if [[ -f "${ZALO_COMMON_ROOT}/scripts/main/patch_zalo_bridge_inject.py" ]]; then
    ZALO_BRIDGE_FORCE_RESTART=1 $ZALO_SUDO python3 "${ZALO_COMMON_ROOT}/scripts/main/patch_zalo_bridge_inject.py" || true
  fi
  loginctl enable-linger "${USER}" 2>/dev/null || true
  if command -v ufw >/dev/null 2>&1; then
    $ZALO_SUDO ufw allow from 172.16.0.0/12 to any port "$ZALO_PORT" proto tcp comment 'docker->zalo' || true
  fi
  zalo_wait_bridge_port || {
    zalo_log "WARN: bridge not listening on :${ZALO_PORT} yet"
    return 1
  }
}

zalo_stop_bridge_service() {
  systemctl --user stop com.hermes.zaloplugin.service 2>/dev/null || true
  systemctl --user stop assistant-zalo.service 2>/dev/null || true
  systemctl --user disable com.hermes.zaloplugin.service 2>/dev/null || true
  systemctl --user disable assistant-zalo.service 2>/dev/null || true
}

zalo_print_qr_instructions() {
  if [[ -t 1 ]]; then
    cat <<EOF

────────────────────────────────────────────────────────────
STEP 1 — Scan Zalo QR (required before any Zalo install)

The QR code will appear below in this terminal (ASCII).
Open Zalo on your phone → (+) → Scan QR code.

Waiting up to ${ZALO_LOGIN_WAIT_S}s…
────────────────────────────────────────────────────────────
EOF
  else
    cat <<EOF

────────────────────────────────────────────────────────────
STEP 1 — Scan Zalo QR (required before any Zalo install)

Not an interactive terminal — open in a browser (forward port ${ZALO_PORT} if remote):
  ${ZALO_QR_URL}

Scan with the Zalo app. Waiting up to ${ZALO_LOGIN_WAIT_S}s…
────────────────────────────────────────────────────────────
EOF
  fi
}

zalo_run_login_cli() {
  hermes-zalo-plugin login \
    || hermes-zalo-plugin setup --relogin \
    || hermes-zalo-plugin setup
}

zalo_qr_login_phase() {
  zalo_log "Zalo QR login (must succeed before bridge stack + zalo-api install)"
  zalo_need_node || return 1
  zalo_install_plugin_package
  zalo_configure_bridge_systemd
  zalo_start_bridge_service || true

  if zalo_bridge_logged_in_now; then
    zalo_log "bridge already logged in — skip QR prompt"
    curl -sf -m 5 "$ZALO_HEALTH_URL" 2>/dev/null || true
    return 0
  fi

  # Background bridge login is headless (no TTY) — stop it so hermes-zalo-plugin login
  # can render the ASCII QR in this SSH session (upstream ZaloClient uses qrcode-terminal).
  zalo_log "stopping bridge for interactive QR login"
  zalo_stop_bridge_service

  zalo_print_qr_instructions

  if [[ -t 1 ]]; then
    zalo_run_login_cli || {
      echo "ERROR: Zalo QR login failed" >&2
      return 1
    }
  else
    zalo_log "WARN: not a TTY — starting bridge; scan QR at ${ZALO_QR_URL}"
    zalo_start_bridge_service || return 1
    curl -sf -X POST "http://127.0.0.1:${ZALO_PORT}/relogin" \
      -H 'Content-Type: application/json' -d '{}' >/dev/null 2>&1 || true
  fi

  zalo_start_bridge_service || return 1

  local health_json=""
  if health_json="$(zalo_wait_bridge_logged_in)"; then
    systemctl --user try-restart com.hermes.zaloplugin.service 2>/dev/null \
      || systemctl --user try-restart assistant-zalo.service 2>/dev/null \
      || true
    printf '%s' "$health_json"
    return 0
  fi

  return 1
}

zalo_teardown_failed_qr() {
  zalo_log "QR login failed — stopping bridge; NOT installing zalo-api or Hermes Zalo plugin"
  zalo_stop_bridge_service
  if [[ -f "${ZALO_COMMON_ROOT}/.env" ]]; then
    if grep -q '^ENABLE_ZALO=' "${ZALO_COMMON_ROOT}/.env"; then
      sed -i 's/^ENABLE_ZALO=.*/ENABLE_ZALO=inactive/' "${ZALO_COMMON_ROOT}/.env" 2>/dev/null || true
    fi
    if grep -q '^WORKER_MESSAGE=' "${ZALO_COMMON_ROOT}/.env"; then
      sed -i 's/^WORKER_MESSAGE=.*/WORKER_MESSAGE=inactive/' "${ZALO_COMMON_ROOT}/.env" 2>/dev/null || true
    fi
  fi
}

zalo_wait_core_for_qr() {
  zalo_log "wait for core services (model-router + OmniRouter — zalo-api not required yet)"
  local tries=60 i=0
  local router_ok=0 omni_ok=0
  local model_port="${MODEL_ROUTER_PORT:-8096}"
  local omni_port="${OMNIROUTER_HOST_PORT:-20129}"

  for i in $(seq 1 "$tries"); do
    router_ok=0
    omni_ok=0
    curl -fsS -m 3 "http://127.0.0.1:${model_port}/health" >/dev/null 2>&1 && router_ok=1
    case "${ENABLE_OMNIROUTER:-active}" in
      1|true|yes|on|active)
        if curl -fsS -m 3 "http://127.0.0.1:${omni_port}/" >/dev/null 2>&1 \
          || curl -fsS -m 3 "http://127.0.0.1:${omni_port}/v1/models" >/dev/null 2>&1; then
          omni_ok=1
        fi
        ;;
      *)
        omni_ok=1
        ;;
    esac
    if [[ "$router_ok" == "1" && "$omni_ok" == "1" ]]; then
      zalo_log "core ready for QR (router + omni)"
      return 0
    fi
    sleep 5
    echo "  waiting (${i}/${tries}) router=${router_ok} omni=${omni_ok}…"
  done
  echo "ERROR: core not ready for QR (need model-router + OmniRouter when enabled)" >&2
  return 1
}

zalo_stack_running() {
  local api_port="${ZALO_API_PORT:-${ADMIN_API_PORT:-8100}}"
  curl -fsS -m 3 "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1
}

zalo_seed_admin() {
  local health_json="${1:-}"
  if [[ -z "$health_json" ]]; then
    health_json="$(curl -sf -m 5 "$ZALO_HEALTH_URL" 2>/dev/null || true)"
  fi
  local disp="${ZALO_ADMIN_DISPLAY_NAME:-}"
  python3 - "$ZALO_ADMIN_FILE" "$health_json" "$disp" <<'PY' || true
import json, os, sys
path, raw, disp = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "").strip()
if not raw:
    raise SystemExit(0)
try:
    data = json.loads(raw)
except Exception:
    raise SystemExit(0)
if data.get("sessionDead") is True:
    print("SKIP admin seed: bridge sessionDead")
    raise SystemExit(0)
own = str(data.get("ownId") or "").strip()
logged = data.get("loggedIn") is True and bool(own)
if not logged and own and data.get("qr") in (None, "", "null"):
    logged = True
if not (logged and own):
    print("SKIP admin seed: bridge not logged in yet (no ownId)")
    raise SystemExit(0)
if os.path.isfile(path):
    for line in open(path, encoding="utf-8"):
        t = line.strip()
        if t and not t.startswith("#"):
            print(f"admin file already set ({path}) — leave unchanged")
            raise SystemExit(0)
os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
line = f"{own}|{disp}" if disp else own
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write("# managed by login-zalo — sole Zalo admin (exactly one)\n")
    f.write(f"{line}\n")
print(f"OK: first-setup admin seeded from Zalo proxy login → {line}")
print(f"     file: {path}")
PY
}

zalo_backup_session() {
  local script="${ZALO_COMMON_ROOT}/scripts/main/backup-zalo-session.sh"
  [[ -f "$script" ]] && bash "$script" || true
}

zalo_restart_all_services() {
  zalo_log "restart bridge + zalo-api + Hermes after successful login"
  systemctl --user try-restart com.hermes.zaloplugin.service 2>/dev/null \
    || systemctl --user try-restart assistant-zalo.service 2>/dev/null \
    || true
  sleep 3
  zalo_heal_sse
  local sse
  sse="$(curl -sf -m 5 "$ZALO_HEALTH_URL" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("sseClients",0))' 2>/dev/null || echo 0)"
  zalo_log "bridge sseClients=${sse:-0} (expect >=1; later: bash scripts/main/heal-zalo-sse.sh)"
}

zalo_env_upsert() {
  local k="$1" v="$2" f="${ZALO_COMMON_ROOT}/.env"
  touch "$f"
  chmod 600 "$f" 2>/dev/null || true
  if grep -q "^${k}=" "$f"; then
    sed -i "s|^${k}=.*|${k}=${v}|" "$f"
  else
    echo "${k}=${v}" >> "$f"
  fi
}
