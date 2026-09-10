#!/usr/bin/env bash
# Load non-secret defaults from docs/config/DEFAULTS.md, then .env, then workers.
set -euo pipefail

_assistant_defaults_md() {
  local root="${ROOT:-}"
  if [[ -z "$root" && -n "${BASH_SOURCE[0]:-}" ]]; then
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  fi
  echo "${root}/docs/config/DEFAULTS.md"
}

load_defaults_md() {
  local md f line key val
  md="${1:-$(_assistant_defaults_md)}"
  [[ -f "$md" ]] || {
    echo "WARN: defaults markdown missing: ${md}" >&2
    return 0
  }
  f="$(mktemp)"
  awk '
    BEGIN { inblock=0 }
    /^```env[[:space:]]*$/ { inblock=1; next }
    /^```[[:space:]]*$/ && inblock { inblock=0; next }
    inblock { print }
  ' "$md" >"$f"

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || continue
    key="${line%%=*}"
    val="${line#*=}"
    if [[ -n "${!key+x}" && -n "${!key}" ]]; then
      continue
    fi
    # shellcheck disable=SC2163
    export "$key=$val"
  done <"$f"
  rm -f "$f"
}

load_env_with_defaults() {
  local root="${ROOT:-}"
  local envf
  if [[ -z "$root" ]]; then
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
    export ROOT="$root"
  fi
  load_defaults_md "${root}/docs/config/DEFAULTS.md"
  envf="${root}/.env"
  if [[ ! -f "$envf" ]]; then
    for cand in /opt/assistant/.env "${HOME}/assistant/.env"; do
      [[ -f "$cand" ]] && { envf="$cand"; ROOT="$(cd "$(dirname "$cand")" && pwd)"; export ROOT; break; }
    done
  fi
  if [[ -f "$envf" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$envf"
    set +a
  else
    echo "WARN: Missing .env — copy .env.example and set secrets first" >&2
  fi
  DOMAIN="${DOMAIN:-localhost}"
  ASSISTANT_DATA_DIR="${ASSISTANT_DATA_DIR:-/data/assistant}"
  HERMES_DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR}}"
  STACK_ROOT="${STACK_ROOT:-/opt/assistant}"
  BACKUP_DIR="${BACKUP_DIR:-/data/assistant/backups}"
  OPENBAO_TOKEN_FILE="${OPENBAO_TOKEN_FILE:-${ASSISTANT_DATA_DIR}/openbao/root-token}"
  if [[ -f "$OPENBAO_TOKEN_FILE" ]]; then
    OPENBAO_DEV_ROOT_TOKEN="$(tr -d '\r\n' < "$OPENBAO_TOKEN_FILE")"
  fi
  export DOMAIN ASSISTANT_DATA_DIR HERMES_DATA_DIR STACK_ROOT BACKUP_DIR
  export OPENBAO_TOKEN_FILE OPENBAO_DEV_ROOT_TOKEN
}
