#!/usr/bin/env bash
# Shared helpers — Ubuntu 24
set -euo pipefail

# Allow caller to pre-set ROOT (required when common.sh is sourced via process substitution)
if [[ -z "${ROOT:-}" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
export ROOT

load_env() {
  # Non-secret defaults from docs/config/DEFAULTS.md, then .env overrides (secrets / host).
  local _ld="${ROOT}/scripts/lib/load-defaults.sh"
  if [[ -f "$_ld" ]]; then
    # shellcheck disable=SC1090
    source "$_ld"
    load_env_with_defaults
    return 0
  fi
  local f="${ROOT}/.env"
  if [[ ! -f "$f" ]]; then
    for cand in /opt/assistant/.env "${HOME}/assistant/.env"; do
      [[ -f "$cand" ]] && { f="$cand"; ROOT="$(cd "$(dirname "$cand")" && pwd)"; export ROOT; break; }
    done
  fi
  if [[ -f "$f" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$f"
    set +a
  else
    echo "WARN: Missing .env at ${ROOT}/.env — using hardcoded fallbacks" >&2
  fi
  DOMAIN="${DOMAIN:-assistant.site}"
  HERMES_DATA_DIR="${HERMES_DATA_DIR:-/data/hermes}"
  STACK_ROOT="${STACK_ROOT:-/opt/assistant}"
  export DOMAIN HERMES_DATA_DIR STACK_ROOT
}

need_root_or_sudo() {
  if [[ "$(id -u)" -ne 0 ]]; then
    SUDO="sudo"
  else
    SUDO=""
  fi
  export SUDO
}

compose() {
  load_env
  local profiles_file="${ROOT}/generated/compose.profiles.env"
  if [[ -f "$profiles_file" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$profiles_file"; set +a
  fi
  docker compose --project-directory "$ROOT" -f "$ROOT/docker/docker-compose.yml" "$@"
}

log() { echo "==> $*"; }

# Resolve Zalo bridge URL for Hermes-in-Docker → host bridge.
# Priority: explicit non-empty/non-auto ZALO_BRIDGE_URL|ZALO_PLUGIN_URL
#        → Docker network gateway of hermes
#        → primary host IPv4 (hostname -I)
#        → host.docker.internal fallback
resolve_zalo_bridge_url() {
  local port="${ZALO_PLUGIN_PORT:-8787}"
  local explicit="${ZALO_BRIDGE_URL:-${ZALO_PLUGIN_URL:-}}"
  if [[ -n "$explicit" && "$explicit" != "auto" ]]; then
    echo "$explicit"
    return 0
  fi
  local gw
  # One gateway per line (range concatenates without separator if we only print .Gateway)
  gw="$(docker inspect hermes -f '{{range .NetworkSettings.Networks}}{{println .Gateway}}{{end}}' 2>/dev/null \
    | awk 'NF && $0 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ { print; exit }' || true)"
  if [[ -n "$gw" ]]; then
    echo "http://${gw}:${port}"
    return 0
  fi
  local hip
  hip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  if [[ -n "$hip" ]]; then
    echo "http://${hip}:${port}"
    return 0
  fi
  echo "http://host.docker.internal:${port}"
}

