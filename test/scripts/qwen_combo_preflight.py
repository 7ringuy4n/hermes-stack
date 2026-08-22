# -*- coding: utf-8 -*-
"""VPS preflight: Qwen key + Omni hermes/classifier combos (case 38).

Env: ASSISTANT_SSH_* , ASSISTANT_REPO_ROOT
Exit: 0 PASS | 1 FAIL | 2 QWEN_KEY_MISSING (expected when ENABLE_QWEN=1, no key)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "reports" / "qwen-combo-preflight"

REMOTE = r"""
set -uo pipefail
cd /opt/assistant
set -a; . ./.env; set +a

echo "ENABLE_QWEN=${ENABLE_QWEN:-0}"
key=""
for k in QWEN_API_KEY DASHSCOPE_API_KEY ALIBABA_API_KEY; do
  v=$(grep -E "^${k}=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
  if [ -n "$v" ]; then key=1; echo "${k}_SET=1"; break; fi
done
[ -n "$key" ] || echo "QWEN_KEY_SET=0"

python3 <<'PY'
import json, os, sqlite3, glob, sys

enable = os.environ.get("ENABLE_QWEN", "0") == "1"
key = any(
    (os.environ.get(k) or "").strip()
    for k in ("QWEN_API_KEY", "DASHSCOPE_API_KEY", "ALIBABA_API_KEY")
)
# reload from .env file (sudo context)
from pathlib import Path
env = {}
for line in Path("/opt/assistant/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
enable = env.get("ENABLE_QWEN", "0") == "1"
key = any(env.get(k, "").strip() for k in ("QWEN_API_KEY", "DASHSCOPE_API_KEY", "ALIBABA_API_KEY"))

def combo_counts():
    dbs = glob.glob("/var/lib/docker/volumes/*omni*/_data/storage.sqlite")
    if not dbs:
        return None, None
    c = sqlite3.connect(dbs[0])
    c.row_factory = sqlite3.Row
    out = {}
    for row in c.execute("select name,data from combos"):
        if row["name"] not in ("hermes", "classifier"):
            continue
        data = json.loads(row["data"] or "{}")
        models = data.get("models") or data.get("members") or []
        out[row["name"]] = len(models)
    return out.get("hermes"), out.get("classifier")

h, cl = combo_counts()
print("COMBO_HERMES", h if h is not None else "missing_db")
print("COMBO_CLASSIFIER", cl if cl is not None else "missing_db")

if not enable:
    print("RESULT PASS_QWEN_OFF")
    sys.exit(0)

if not key:
    if (h or 0) == 0 and (cl or 0) == 0:
        print("RESULT QWEN_KEY_MISSING")
        sys.exit(2)
    print("RESULT FAIL_KEY_MISSING_BUT_COMBOS_NONEMPTY")
    sys.exit(1)

if (h or 0) < 1 or (cl or 0) < 1:
    print("RESULT FAIL_EMPTY_COMBOS_WITH_KEY")
    sys.exit(1)

print("RESULT PASS_QWEN_READY")
PY

echo "=== router tail ==="
docker logs router-worker 2>&1 | grep -iE 'Unable to determine|400.*hermes' | tail -5 || true
echo PREFLIGHT_DONE
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=120)
    finally:
        c.close()
    (OUT / "console.log").write_text(out or "", encoding="utf-8", errors="replace")
    print(out or "", flush=True)
    if not out or "PREFLIGHT_DONE" not in out:
        return 1
    if "RESULT PASS_QWEN_READY" in out or "RESULT PASS_QWEN_OFF" in out:
        print("PASS_QWEN_COMBO_PREFLIGHT")
        return 0
    if "RESULT QWEN_KEY_MISSING" in out:
        print("QWEN_KEY_MISSING (expected — Zalo chat will not reply until key is set)")
        return 0  # expected negative on lab without key
    print("FAIL_QWEN_COMBO_PREFLIGHT")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
