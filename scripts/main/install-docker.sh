#!/usr/bin/env bash
# First-setup: install Docker CE + Compose plugin if missing (Ubuntu/Debian).
# Usage:
#   sudo bash scripts/main/install-docker.sh           # uses the SSH/login user who ran sudo
#   sudo bash scripts/main/install-docker.sh alice     # optional explicit username
#
# Target user resolution (first match wins):
#   1) $1 argument
#   2) $SUDO_USER (user who invoked sudo over SSH)
#   3) logname / `who am i` (login session)
#   4) $USER if not root
set -euo pipefail

resolve_login_user() {
  local u=""
  if [[ -n "${1:-}" ]]; then
    printf '%s\n' "$1"
    return 0
  fi
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    printf '%s\n' "$SUDO_USER"
    return 0
  fi
  u="$(logname 2>/dev/null || true)"
  if [[ -n "$u" && "$u" != "root" ]]; then
    printf '%s\n' "$u"
    return 0
  fi
  u="$(who am i 2>/dev/null | awk '{print $1}' || true)"
  if [[ -n "$u" && "$u" != "root" ]]; then
    printf '%s\n' "$u"
    return 0
  fi
  if [[ -n "${USER:-}" && "${USER}" != "root" ]]; then
    printf '%s\n' "$USER"
    return 0
  fi
  return 1
}

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root via sudo so the SSH login user is preserved, e.g.:" >&2
  echo "  sudo bash $0" >&2
  exit 1
fi

if ! TARGET_USER="$(resolve_login_user "${1:-}")"; then
  echo "Cannot detect login user (running as root with no SUDO_USER)." >&2
  echo "Pass the SSH username explicitly: sudo bash $0 <username>" >&2
  exit 1
fi

echo "==> docker group target user: ${TARGET_USER}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "==> Docker already installed: $(docker --version)"
  docker compose version
else
  export DEBIAN_FRONTEND=noninteractive
  . /etc/os-release
  CODENAME="${VERSION_CODENAME:-jammy}"

  echo "==> apt update"
  apt-get update -y

  echo "==> prerequisites + Docker apt repo"
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${CODENAME} stable" \
    >/etc/apt/sources.list.d/docker.list

  apt-get update -y
  echo "==> apt-cache policy docker-ce"
  apt-cache policy docker-ce || true

  echo "==> install docker-ce + plugins"
  apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

  systemctl enable --now docker
fi

echo "==> docker status"
systemctl status docker --no-pager || true

echo "==> add ${TARGET_USER} to docker group"
groupadd docker 2>/dev/null || true
usermod -aG docker "${TARGET_USER}"

echo "==> verify group"
getent group docker

echo
echo "OK: Docker ready. ${TARGET_USER} must re-login (or: newgrp docker) before using docker without sudo."
