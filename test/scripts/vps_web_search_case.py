# -*- coding: utf-8 -*-
"""Case 18: probe dispatcher web search backends on VPS (SSH).

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
echo "WEB_BACKENDS=${WEB_BACKENDS:-empty}"
echo "SEARXNG_URL=${SEARXNG_URL:-unset}"
curl -sS -m 10 http://127.0.0.1:8090/health || echo HEALTH_FAIL
echo
code=$(curl -sS -m 45 -o /tmp/search.json -w "%{http_code}" \
  -X POST http://127.0.0.1:8090/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"weather Ho Chi Minh","max_results":3}' || echo 000)
echo "SEARCH_HTTP=$code"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/search.json")
if not p.exists():
    print("SEARCH_BODY=missing")
    raise SystemExit
raw = p.read_text(encoding="utf-8", errors="replace")[:800]
print("SEARCH_BODY=" + raw.replace("\n", " ")[:800])
try:
    d = json.loads(p.read_text(encoding="utf-8"))
except Exception:
    print("BACKEND=parse_error")
    raise SystemExit
print("BACKEND=" + str(d.get("backend") or d.get("source") or "unknown"))
PY
echo CASE18_DONE
""",
            timeout=90,
        )
        print(out[-1200:])
        if "CASE18_DONE" not in out:
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

