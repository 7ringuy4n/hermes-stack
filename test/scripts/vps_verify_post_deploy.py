# -*- coding: utf-8 -*-
"""Quick post-deploy verify: omni-router auth, Hermes network, cron, admin (stdout only)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
cid=$(docker ps -q --filter name=hermes | head -1)
echo "HERMES_CID=${cid}"
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
curl -fsS -m 10 -H "Authorization: Bearer ${OMNIROUTER_API_KEY}" http://127.0.0.1:20128/v1/models \
  | python3 -c 'import sys,json; m=json.load(sys.stdin); d=m.get("data",[]); print("models_ok", len(d))'
set +e
docker exec -e "OMNIROUTER_API_KEY=${OMNIROUTER_API_KEY}" "${cid}" python3 -c \
  "import os,urllib.request; k=os.environ.get('OMNIROUTER_API_KEY',''); req=urllib.request.Request('http://omni-router:20129/v1/models', headers={'Authorization':'Bearer '+k}); r=urllib.request.urlopen(req, timeout=8); print('hermes_to_omni-router', r.status)" \
  || echo "hermes_to_omni-router=fail"
set -e
docker exec "${cid}" hermes cron list 2>/dev/null | head -15 || echo "(no cron list)"
python3 - <<'PY'
from pathlib import Path
env = {}
for line in Path("/opt/assistant/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
for k in (
    "ASSISTANT_PROFILE",
    "HERMES_REPLICAS",
    "ENABLE_ZALO",
    "HERMES_DASHBOARD_USER",
    "HERMES_DASHBOARD_PASSWORD",
    "GRAFANA_ADMIN_USER",
    "GRAFANA_ADMIN_PASSWORD",
    "OMNIROUTER_INITIAL_PASSWORD",
):
    print(f"{k}={env.get(k, '')}")
PY
echo VERIFY_DONE
""",
            timeout=120,
        )
        sys.stdout.write(out)
        return 0 if "VERIFY_DONE" in out else 1
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

