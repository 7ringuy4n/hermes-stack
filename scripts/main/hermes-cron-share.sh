#!/usr/bin/env bash
# Promote replica Hermes cron jobs into the shared data dir, then prune stale replica homes.
# Safe to run while the stack is up. Does not print job payloads.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
export HERMES_DATA_DIR="$DATA"
python3 "${ROOT}/architect/backup-restore/lib/hermes_cron_share.py" "$@"
