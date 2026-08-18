# -*- coding: utf-8 -*-
"""Post-deploy health: Hermes, 9router, Traefik, Zalo — no host/secrets in output."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_high import connect, sudo_bash  # noqa: E402

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
echo "hermes1=$(docker inspect -f '{{.State.Status}}' assistant-hermes-1 2>/dev/null || echo missing)"
echo "hermes2=$(docker inspect -f '{{.State.Status}}' assistant-hermes-2 2>/dev/null || echo missing)"
echo "zalo_api=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8100/health || echo fail)"
echo "traefik=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/health || echo fail)"
echo "dispatcher=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8090/health || echo fail)"
echo "model_router=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8096/health || echo fail)"
echo "9router_root=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:20128/ || echo fail)"
echo "9router_models=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:20128/v1/models || echo fail)"
# From Hermes container to 9router on docker network
echo -n "hermes_to_9router="
docker exec assistant-hermes-1 python3 -c "import urllib.request; urllib.request.urlopen('http://9router:20128/', timeout=5); print('ok')" 2>/dev/null || echo fail
echo -n "hermes_to_model_router="
docker exec assistant-hermes-1 python3 -c "import urllib.request; urllib.request.urlopen('http://model-router:8096/health', timeout=5); print('ok')" 2>/dev/null || echo fail
test -f /opt/assistant/hermes/main/plugins/zalo/multi_request.py && echo files_multi=ok || echo files_multi=missing
test -f /opt/assistant/hermes/main/plugins/zalo/inbound_queue.py && echo files_queue=ok || echo files_queue=missing
test -f /opt/assistant/architect/tools/schedule_tz.py && echo files_tz=ok || echo files_tz=missing
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
