#!/usr/bin/env bash
# Sync model-router prompt/config SoT from Hermes skills → bake fallback under
# architect/models/model-router/config/ (Docker image COPY).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DST_DIR="$ROOT/architect/models/model-router/config"
mkdir -p "$DST_DIR"

sync_one() {
  local src="$1"
  local name="$2"
  if [[ ! -f "$src" ]]; then
    echo "missing SoT: $src" >&2
    exit 1
  fi
  cp -f "$src" "$DST_DIR/$name"
  echo "synced $name ← $src"
}

sync_one "$ROOT/hermes/main/skills/classify/classify.json" "classify.json"
sync_one "$ROOT/hermes/main/skills/outbound/outbound.json" "outbound.json"
sync_one "$ROOT/hermes/main/skills/web-search/web-search-combo.json" "web-search-combo.json"

# heuristic.json is not a skill SoT — never loaded; do not reintroduce as keyword NLU.
if [[ -f "$DST_DIR/heuristic.json" ]]; then
  rm -f "$DST_DIR/heuristic.json"
  echo "removed unused bake copy heuristic.json"
fi
