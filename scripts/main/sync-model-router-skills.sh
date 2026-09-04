#!/usr/bin/env bash
# Sync model-router prompt/config SoT from Hermes skills → bake fallback under
# architect/models/model-router/config/ (Docker image COPY).
# Classify bake is assembled from skills/classify/parts (one system string, one hop).
#
# Ownership: a prior root/sudo sync can leave classify.json root-owned while the
# operator runs as a normal user (PermissionError on write). Always write via a
# temp file and restore ownership to match the destination directory.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DST_DIR="$ROOT/architect/models/model-router/config"
mkdir -p "$DST_DIR"

if [[ "$(id -u)" -ne 0 ]] || [[ -w "$DST_DIR" ]]; then
  exec python3 "$ROOT/scripts/main/sync_model_router_skills.py"
fi

_dst_owner() {
  # Prefer directory owner so git checkout trees stay operator-writable.
  if command -v stat >/dev/null 2>&1; then
    if stat -c '%u:%g' "$DST_DIR" >/dev/null 2>&1; then
      stat -c '%u:%g' "$DST_DIR"
      return 0
    fi
    if stat -f '%u' "$DST_DIR" >/dev/null 2>&1; then
      echo "$(stat -f '%u' "$DST_DIR"):$(stat -f '%g' "$DST_DIR")"
      return 0
    fi
  fi
  echo "$(id -u):$(id -g)"
}

_install_file() {
  local src="$1"
  local dst="$2"
  local owner
  owner="$(_dst_owner)"
  if [[ -e "$dst" ]] && [[ ! -w "$dst" ]]; then
    # Common case: root-owned file in an operator-writable directory.
    if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
      sudo -n rm -f "$dst"
    else
      echo "cannot replace non-writable $dst — run: sudo chown ${owner} $dst" >&2
      rm -f "$src"
      exit 1
    fi
  fi
  if [[ -w "$(dirname "$dst")" ]]; then
    mv -f "$src" "$dst"
  elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo -n mv -f "$src" "$dst"
  else
    echo "cannot write $dst — run: sudo chown -R ${owner} $(dirname "$dst")" >&2
    rm -f "$src"
    exit 1
  fi
  # Keep the bake tree operator-owned so the next non-root update works.
  if [[ "$(id -u)" -eq 0 ]]; then
    chown "$owner" "$dst" 2>/dev/null || true
  elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo -n chown "$owner" "$dst" 2>/dev/null || true
  fi
  chmod u+rw,go+r "$dst" 2>/dev/null || true
}

sync_one() {
  local src="$1"
  local name="$2"
  if [[ ! -f "$src" ]]; then
    echo "missing SoT: $src" >&2
    exit 1
  fi
  local tmp
  tmp="$(mktemp "${DST_DIR}/.${name}.XXXXXX")"
  cp -f "$src" "$tmp"
  _install_file "$tmp" "$DST_DIR/$name"
  echo "synced $name ← $src"
}

# Assemble classify skill parts into a self-contained bake JSON (no parts/ in the image).
CLASSIFY_TMP="$(
  python3 - "$ROOT" "$DST_DIR" <<'PY'
import json
import sys
import tempfile
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
fd, tmp_name = tempfile.mkstemp(prefix=".classify.json.", dir=str(dst_dir))
tmp_path = Path(tmp_name)
try:
    with open(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
except Exception:
    tmp_path.unlink(missing_ok=True)
    raise
print(f"assembled classify.json ← {len(chunks)} parts", file=sys.stderr)
print(tmp_path)
PY
)"

_install_file "$CLASSIFY_TMP" "$DST_DIR/classify.json"
echo "assembled classify.json → $DST_DIR/classify.json"

sync_one "$ROOT/hermes/main/skills/outbound/outbound.json" "outbound.json"

if [[ -f "$DST_DIR/web-search-combo.json" ]]; then
  rm -f "$DST_DIR/web-search-combo.json"
  echo "removed unused bake copy web-search-combo.json"
fi

if [[ -f "$DST_DIR/heuristic.json" ]]; then
  rm -f "$DST_DIR/heuristic.json"
  echo "removed unused bake copy heuristic.json"
fi
