#!/usr/bin/env bash
# Thin wrapper — see first-setup-9router-hermes.py
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export STACK_ROOT="${STACK_ROOT:-/opt/assistant}"
export HERMES_DATA_DIR="${HERMES_DATA_DIR:-/data/assistant}"
exec python3 "${ROOT}/scripts/main/first-setup-9router-hermes.py" "$@"
