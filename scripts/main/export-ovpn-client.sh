#!/usr/bin/env bash
# Export a new OpenVPN client .ovpn and chown into the operator home folder.
# Usage: CLIENT_NAME=alice bash scripts/main/export-ovpn-client.sh
set -euo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a

case "${ENABLE_OPENVPN:-0}" in
  1|true|yes|on) ;;
  *) echo "export-ovpn: ENABLE_OPENVPN!=1 — enable OpenVPN first"; exit 1 ;;
esac

CLIENT_NAME="${CLIENT_NAME:-client1}"
# Sanitize client name (no path injection)
case "$CLIENT_NAME" in
  *[!A-Za-z0-9._-]*|"") echo "invalid CLIENT_NAME"; exit 1 ;;
esac

OPENVPN_DATA="${OPENVPN_DATA_DIR:-/data/assistant/openvpn}"
TARGET_USER="${OVPN_EXPORT_USER:-${SUDO_USER:-${USER:-}}}"
if [[ -z "$TARGET_USER" ]]; then
  echo "export-ovpn: set OVPN_EXPORT_USER or run via sudo from a login user"
  exit 1
fi
HOME_DIR="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
[[ -n "$HOME_DIR" ]] || HOME_DIR="/home/${TARGET_USER}"
OUT_DIR="${OVPN_EXPORT_DIR:-${HOME_DIR}/assistant-ovpn}"
if [[ "$(id -u)" -ne 0 ]]; then SUDO=sudo; else SUDO=; fi

echo "==> export OpenVPN client=${CLIENT_NAME} → ${OUT_DIR}"
$SUDO mkdir -p "$OUT_DIR"
# kylemanna/openvpn helper on the running container
if ! docker ps --format '{{.Names}}' | grep -qx openvpn; then
  echo "openvpn container not running"; exit 1
fi
$SUDO docker run --rm -v "${OPENVPN_DATA}:/etc/openvpn" "${OPENVPN_IMAGE:-kylemanna/openvpn}" \
  easyrsa build-client-full "$CLIENT_NAME" nopass 2>/dev/null || true
$SUDO docker run --rm -v "${OPENVPN_DATA}:/etc/openvpn" "${OPENVPN_IMAGE:-kylemanna/openvpn}" \
  ovpn_getclient "$CLIENT_NAME" | $SUDO tee "${OUT_DIR}/${CLIENT_NAME}.ovpn" >/dev/null
$SUDO chown -R "${TARGET_USER}:${TARGET_USER}" "$OUT_DIR"
$SUDO chmod 600 "${OUT_DIR}/${CLIENT_NAME}.ovpn"
echo "OK: ${OUT_DIR}/${CLIENT_NAME}.ovpn"
