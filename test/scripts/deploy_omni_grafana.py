# -*- coding: utf-8 -*-
"""Deploy OmniRoute Grafana exporter + dashboards to the VPS."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import ROOT, connect, sftp_put, sudo_bash, _file_bytes  # noqa: E402

FILES = [
    ("architect/monitor/omni-exporter/app.py", "/tmp/omni-exporter-app.py"),
    ("docker/docker-compose.security.yml", "/tmp/docker-compose.security.yml"),
    ("config/monitor/prometheus.yml", "/tmp/prometheus.yml"),
    ("config/monitor/grafana/dashboards/json/assistant-overview.json", "/tmp/assistant-overview.json"),
    ("config/monitor/grafana/dashboards/json/assistant-logs.json", "/tmp/assistant-logs.json"),
    ("config/monitor/grafana/dashboards/json/assistant-file-flow.json", "/tmp/assistant-file-flow.json"),
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
install -m 0644 /tmp/omni-exporter-app.py /opt/assistant/architect/monitor/omni-exporter/app.py
install -m 0644 /tmp/docker-compose.security.yml /opt/assistant/docker/docker-compose.security.yml
install -m 0644 /tmp/prometheus.yml /opt/assistant/config/monitor/prometheus.yml
install -m 0644 /tmp/assistant-overview.json /opt/assistant/config/monitor/grafana/dashboards/json/assistant-overview.json
install -m 0644 /tmp/assistant-logs.json /opt/assistant/config/monitor/grafana/dashboards/json/assistant-logs.json
install -m 0644 /tmp/assistant-file-flow.json /opt/assistant/config/monitor/grafana/dashboards/json/assistant-file-flow.json
sed -i 's/\r$//' /opt/assistant/architect/monitor/omni-exporter/app.py \
  /opt/assistant/docker/docker-compose.security.yml \
  /opt/assistant/config/monitor/prometheus.yml
cd /opt/assistant
set -a
. ./.env
set +a
export COMPOSE_PROGRESS=plain ASSISTANT_PROFILE=high
files="-f /opt/assistant/docker/docker-compose.yml -f /opt/assistant/docker/docker-compose.media.yml -f /opt/assistant/docker/docker-compose.security.yml"
docker compose --project-directory /opt/assistant $files --profile prometheus --profile grafana --profile omni-exporter --profile omnirouter build omni-exporter omni-exporter
docker compose --project-directory /opt/assistant $files --profile prometheus --profile grafana --profile omni-exporter --profile omnirouter up -d --no-deps --force-recreate omni-exporter omni-exporter prometheus grafana stack-exporter
sleep 8
curl -fsS -m 5 http://127.0.0.1:9104/metrics >/dev/null 2>&1 || curl -sS -m 5 http://omni-exporter:9104/metrics >/dev/null 2>&1 || true
docker exec omni-exporter wget -qO- http://127.0.0.1:9104/metrics 2>/dev/null | head -n 8 || docker exec omni-exporter python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9104/metrics', timeout=5).read()[:400].decode())"
docker ps --filter name=omni-exporter --format '{{.Names}} {{.Status}}'
echo OMNI_GRAFANA_DONE
""",
            timeout=600,
        )
        if "OMNI_GRAFANA_DONE" not in out:
            print("FAIL missing OMNI_GRAFANA_DONE")
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

