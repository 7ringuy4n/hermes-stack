# -*- coding: utf-8 -*-
"""Sync source and finish Zalo setup after partial deploy_high (no destroy)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash, sync_tree  # noqa: E402

PW = os.environ["ASSISTANT_SSH_PASSWORD"]
esc = PW.replace("'", "'\\''")
USER = os.environ["ASSISTANT_SSH_USER"]


def main() -> int:
    c = connect()
    try:
        sync_tree(c)
        out = sudo_bash(
            c,
            f"""
set -euo pipefail
cd /opt/assistant
export COMPOSE_PROGRESS=plain
echo "=== SETUP ZALO ==="
linger_uid=$(id -u {USER})
loginctl enable-linger {USER} || true
sudo -u {USER} -H env \\
  XDG_RUNTIME_DIR=/run/user/${{linger_uid}} \\
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${{linger_uid}}/bus \\
  ASSISTANT_SUDO_PASSWORD='{esc}' \\
  ENABLE_ZALO=1 \\
  bash /opt/assistant/scripts/main/setup-zalo.sh
echo "=== CHECK HIGH ==="
bash run.sh check-security
echo "=== ROUTER ==="
set +e
set -a; . ./.env; set +a
curl -fsS -m 10 -H "Authorization: Bearer ${{N9ROUTER_API_KEY:-}}" http://127.0.0.1:20128/v1/models | head -c 200; echo
router_rc=$?
set -e
echo ROUTER_RC=$router_rc
echo "=== CRON ==="
cid=$(docker ps -q --filter name=hermes | head -1)
if [[ -n "$cid" ]]; then docker exec "$cid" hermes cron list 2>/dev/null | head -20 || true; fi
echo "=== BRIDGE ==="
curl -fsS -m 8 http://127.0.0.1:8787/health || echo BRIDGE_DOWN
echo
echo "=== ADMIN ==="
python3 - <<'PY'
from pathlib import Path
env = {{}}
for line in Path("/opt/assistant/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
for k in ("HERMES_DASHBOARD_USER", "HERMES_DASHBOARD_PASSWORD", "GRAFANA_ADMIN_USER", "GRAFANA_ADMIN_PASSWORD", "N9ROUTER_INITIAL_PASSWORD"):
    print(f"{{k}}={{env.get(k, '')}}")
PY
echo RESUME_DONE
""",
            timeout=1200,
        )
        if "RESUME_DONE" not in out:
            print("FAIL: missing RESUME_DONE", file=sys.stderr)
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

