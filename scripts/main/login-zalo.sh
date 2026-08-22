#!/usr/bin/env bash
# Zalo QR login / re-login for the host bridge.
#
# First setup: prefer bash scripts/main/setup-zalo.sh (QR then installs zalo-api).
# Re-login when stack already running: bash scripts/main/login-zalo.sh
#
# Run as deploy user (not root).
#
# Attribution: bridge by Cường Tuấn Nguyễn (cuongdev) — hermes-zalo-plugin (MIT).
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
source "${ROOT}/scripts/main/zalo-common.sh"

zalo_ensure_deploy_user
zalo_ensure_config_writable

echo "==> Zalo login (https://github.com/cuongdev/hermes-zalo-plugin)"
echo

if ! zalo_stack_running; then
  echo "NOTE: zalo-api is not up yet — use setup-zalo for first install:" >&2
  echo "  bash scripts/main/setup-zalo.sh" >&2
  echo >&2
fi

local_health=""
if ! local_health="$(zalo_qr_login_phase)"; then
  zalo_teardown_failed_qr
  echo "ERROR: QR login failed — Zalo bridge not logged in" >&2
  exit 1
fi

echo
echo "--- health ---"
echo "$local_health" | head -c 500
echo

zalo_seed_admin "$local_health"
zalo_backup_session

if zalo_stack_running; then
  zalo_restart_all_services
else
  echo
  echo "QR OK. Complete first-time install:"
  echo "  bash scripts/main/setup-zalo.sh"
  echo "(setup-zalo will skip QR if already logged in)"
fi

echo
echo "Admin (sole): !zalo claim  then  !zalo admin transfer @tag"
echo "Session backup: \$ASSISTANT_DATA_DIR/zalo-session-backup/credentials.json"
