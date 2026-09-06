# -*- coding: utf-8 -*-
"""VPS preflight: Omni hermes/classifier combos have members (case 38).

Env: ASSISTANT_SSH_* , ASSISTANT_REPO_ROOT
Exit: 0 PASS | 1 FAIL
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "reports" / "omni-combo-preflight"

REMOTE = r"""
set -uo pipefail
cd /opt/assistant

python3 <<'PY'
import json, sqlite3, sys
from pathlib import Path

dbs = list(Path("/var/lib/docker/volumes").glob("*omni*/_data/storage.sqlite"))
if not dbs:
    print("COMBO_HERMES missing_db")
    print("COMBO_CLASSIFIER missing_db")
    print("RESULT FAIL_MISSING_OMNI_DB")
    sys.exit(1)
conn = sqlite3.connect(str(dbs[0]))
conn.row_factory = sqlite3.Row
counts = {"hermes": 0, "classifier": 0}
for row in conn.execute("select name,data from combos"):
    name = row["name"]
    if name not in counts:
        continue
    data = json.loads(row["data"] or "{}")
    models = data.get("models") or data.get("members") or []
    counts[name] = len(models) if isinstance(models, list) else 0
print("COMBO_HERMES", counts["hermes"])
print("COMBO_CLASSIFIER", counts["classifier"])
if counts["hermes"] < 1 or counts["classifier"] < 1:
    print("RESULT FAIL_EMPTY_COMBOS")
    sys.exit(1)
print("RESULT PASS_OPENCODE_COMBOS")
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
    if "RESULT PASS_OPENCODE_COMBOS" in out:
        print("PASS_OMNI_COMBO_PREFLIGHT")
        return 0
    print("FAIL_OMNI_COMBO_PREFLIGHT")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
