#!/usr/bin/env bash
# Thin wrapper — see first-setup-omnirouter.py
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export STACK_ROOT="${STACK_ROOT:-/opt/assistant}"
exec python3 "${ROOT}/scripts/main/first-setup-omnirouter.py" "$@"
