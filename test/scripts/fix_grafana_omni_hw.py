# -*- coding: utf-8 -*-
"""Fix OmniRouter scrape 404 and add node-exporter for hardware panels."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import ROOT, connect, sftp_put, sudo_bash, _file_bytes  # noqa: E402

FILES = [
    ("architect/monitor/nine-exporter/app.py", "/tmp/nine-exporter-app.py"),
    ("docker/docker-compose.security.yml", "/tmp/docker-compose.security.yml"),
    ("config/monitor/prometheus.yml", "/tmp/prometheus.yml"),
]


def main() -> int:
    c = connect()
    try:
        for rel, remote in FILES:
            sftp_put(c, _file_bytes(ROOT / Path(*rel.split("/"))), remote)
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
install -m 0644 /tmp/nine-exporter-app.py /opt/assistant/architect/monitor/nine-exporter/app.py
install -m 0644 /tmp/docker-compose.security.yml /opt/assistant/docker/docker-compose.security.yml
install -m 0644 /tmp/prometheus.yml /opt/assistant/config/monitor/prometheus.yml
sed -i 's/\r$//' /opt/assistant/architect/monitor/nine-exporter/app.py \
  /opt/assistant/docker/docker-compose.security.yml /opt/assistant/config/monitor/prometheus.yml
cd /opt/assistant
set -a
. ./.env
set +a
export COMPOSE_PROGRESS=plain
files="-f /opt/assistant/docker/docker-compose.yml -f /opt/assistant/docker/docker-compose.media.yml -f /opt/assistant/docker/docker-compose.security.yml"
docker compose --project-directory /opt/assistant $files --profile prometheus --profile grafana --profile omni-exporter --profile omnirouter build nine-exporter omni-exporter
docker compose --project-directory /opt/assistant $files --profile prometheus --profile grafana --profile omni-exporter --profile omnirouter up -d --no-deps --force-recreate nine-exporter omni-exporter node-exporter prometheus
sleep 10
echo "=== OMNI scrape ==="
docker exec omni-exporter python -c "
import urllib.request
t=urllib.request.urlopen('http://127.0.0.1:9104/metrics', timeout=8).read().decode()
for line in t.splitlines():
    if not line or line.startswith('#'):
        continue
    if any(x in line for x in ('scrape_success','scrape_error','combos','models ')):
        print(line[:200])
"
echo "=== NODE exporter up? ==="
docker ps --filter name=node-exporter --format '{{.Names}} {{.Status}}'
docker exec prometheus wget -qO- 'http://node-exporter:9100/metrics' 2>/dev/null | grep -m2 node_memory_MemAvailable || \
  docker exec prometheus python3 -c "
import urllib.request
t=urllib.request.urlopen('http://node-exporter:9100/metrics', timeout=8).read().decode()
print('node_memory', 'node_memory_MemAvailable_bytes' in t, 'node_cpu', 'node_cpu_seconds_total' in t)
"
echo GRAFANA_FIX_DONE
""",
            timeout=300,
        )
        if "GRAFANA_FIX_DONE" not in out:
            print("FAIL missing GRAFANA_FIX_DONE")
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

