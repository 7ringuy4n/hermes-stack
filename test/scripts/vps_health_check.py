# -*- coding: utf-8 -*-
"""Post-deploy health: Hermes, omni-router, Traefik, Zalo â€” no host/secrets in output."""
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
omni_host_port="${OMNIROUTER_HOST_PORT:-20129}"
case "${omni_host_port}" in (*[!0-9]*|'') echo "omni-router_host_port=invalid"; exit 1;; esac
cid=$(docker ps -q --filter name=hermes | head -1)
echo "hermes=$(docker inspect -f '{{.State.Status}}' "${cid}" 2>/dev/null || echo missing)"
echo "hermes_name=$(docker inspect -f '{{.Name}}' "${cid}" 2>/dev/null | tr -d / || echo missing)"
echo "zalo_api=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8100/health || echo fail)"
echo "traefik=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/health || echo fail)"
echo "dispatcher=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8090/health || echo fail)"
echo "router_worker=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8096/health || echo fail)"
echo "omni-router_root=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${omni_host_port}/" || echo fail)"
# From Hermes container to omni-router on docker network
echo -n "hermes_to_omni-router="
docker exec "${cid}" python3 -c "import os,urllib.request; k=os.environ.get('OMNIROUTER_API_KEY',''); req=urllib.request.Request('http://omni-router:20129/v1/models', headers={'Authorization':'Bearer '+k}); urllib.request.urlopen(req, timeout=5); print('ok')"
echo -n "hermes_to_router_worker="
docker exec "${cid}" python3 -c "import urllib.request; urllib.request.urlopen('http://router-worker:8096/health', timeout=5); print('ok')"
test -f /opt/assistant/hermes/main/plugins/zalo/multi_request.py; echo files_multi=ok
test -f /opt/assistant/hermes/main/plugins/zalo/inbound_queue.py; echo files_queue=ok
test -f /opt/assistant/architect/tools/schedule_tz.py; echo files_tz=ok
echo HEALTH_DONE
""",
            timeout=60,
        )
        print(out[-2000:])
        return 0 if "HEALTH_DONE" in out else 1
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

