# -*- coding: utf-8 -*-
"""Point stack-exporter OmniRoute probe at GET / (no /health)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import ROOT, connect, sftp_put, sudo_bash, _file_bytes  # noqa: E402


def main() -> int:
    c = connect()
    try:
        sftp_put(
            c,
            _file_bytes(ROOT / "docker" / "docker-compose.security.yml"),
            "/tmp/docker-compose.security.yml",
        )
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
install -m 0644 /tmp/docker-compose.security.yml /opt/assistant/docker/docker-compose.security.yml
sed -i 's/\r$//' /opt/assistant/docker/docker-compose.security.yml
cd /opt/assistant
set -a
. ./.env
set +a
export COMPOSE_PROGRESS=plain
files="-f /opt/assistant/docker/docker-compose.yml -f /opt/assistant/docker/docker-compose.media.yml -f /opt/assistant/docker/docker-compose.security.yml"
docker compose --project-directory /opt/assistant $files --profile prometheus --profile omni-exporter --profile omnirouter up -d --no-deps --force-recreate stack-exporter
sleep 35
echo '=== HEALTH_TARGETS ==='
docker inspect stack-exporter --format '{{range .Config.Env}}{{println .}}{{end}}' | grep HEALTH
echo '=== assistant_service_up omni ==='
docker exec stack-exporter python -c '
import urllib.request
t=urllib.request.urlopen("http://127.0.0.1:9102/metrics", timeout=8).read().decode()
for line in t.splitlines():
    if "assistant_service_up" in line and "omni" in line:
        print(line)
'
echo OMNI_HEALTH_FIX_DONE
""",
            timeout=180,
        )
        if "OMNI_HEALTH_FIX_DONE" not in out:
            print("FAIL missing OMNI_HEALTH_FIX_DONE")
            return 1
        if 'assistant_service_up{service="omni-router"} 1.0' not in out.replace(" ", ""):
            # metric may include spaces: `} 1.0`
            if 'service="omni-router"} 1.0' not in out and 'service="omni-router"} 1' not in out:
                print("FAIL omni-router still not UP")
                return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

