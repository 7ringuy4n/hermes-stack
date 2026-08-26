#!/usr/bin/env bash
# Sync model-router prompt/config SoT from Hermes skills → bake fallback under
# architect/models/model-router/config/ (Docker image COPY).
# Classify bake is assembled from skills/classify/parts (one system string, one hop).
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

# Assemble classify skill parts into a self-contained bake JSON (no parts/ in the image).
python3 - "$ROOT" "$DST_DIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
dst_dir = Path(sys.argv[2])
skill = root / "hermes" / "main" / "skills" / "classify"
env_path = skill / "classify.json"
data = json.loads(env_path.read_text(encoding="utf-8"))
names = data.get("parts") or []
chunks = []
for name in names:
    name = str(name or "").strip()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise SystemExit(f"invalid classify part name: {name!r}")
    part = skill / "parts" / f"{name}.txt"
    if not part.is_file():
        raise SystemExit(f"missing classify part: {part}")
    text = part.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"empty classify part: {part}")
    chunks.append(text)
if not chunks:
    raise SystemExit("classify parts produced empty system")
data["system"] = "\n\n".join(chunks)
dst = dst_dir / "classify.json"
dst.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"assembled classify.json ← {len(chunks)} parts → {dst}")
PY

sync_one "$ROOT/hermes/main/skills/outbound/outbound.json" "outbound.json"
sync_one "$ROOT/hermes/main/skills/web-search/web-search-combo.json" "web-search-combo.json"

if [[ -f "$DST_DIR/heuristic.json" ]]; then
  rm -f "$DST_DIR/heuristic.json"
  echo "removed unused bake copy heuristic.json"
fi
