#!/usr/bin/env bash
# Compatibility shim — implementation lives in workers.sh
set -euo pipefail
# shellcheck source=workers.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/workers.sh"
