#!/usr/bin/env bash
# DEPRECATED (filename only). Current flow uses `bash run.sh check-media`.
set -euo pipefail

exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/check-media.sh" "$@"
