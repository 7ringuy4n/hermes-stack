# -*- coding: utf-8 -*-
"""Diagnose OmniRouter Grafana DOWN and missing hardware metrics."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

REMOTE = r"""
set -euo pipefail
echo "=== CONTAINERS ==="
docker ps --format '{{.Names}} {{.Status}}' | grep -E 'omni|nine|prom|grafana|node' || true
echo "=== OMNI-EXPORTER METRICS (prefix lines) ==="
docker exec omni-exporter python -c "
import urllib.request
t=urllib.request.urlopen('http://127.0.0.1:9104/metrics', timeout=8).read().decode()
for line in t.splitlines():
    if line.startswith('#') or not line.strip():
        continue
    if 'scrape_success' in line or 'scrape_error' in line or 'requests_total' in line:
        print(line[:220])
" || echo OMNI_EXPORTER_FAIL
echo "=== NINE-EXPORTER scrape_success ==="
docker exec nine-exporter python -c "
import urllib.request
t=urllib.request.urlopen('http://127.0.0.1:9101/metrics', timeout=8).read().decode()
for line in t.splitlines():
    if 'scrape_success' in line and not line.startswith('#'):
        print(line[:220])
" || echo NINE_EXPORTER_FAIL
echo "=== PROM TARGETS ==="
docker exec prometheus wget -qO- 'http://127.0.0.1:9090/api/v1/targets' 2>/dev/null | python3 -c "
import sys, json
raw=sys.stdin.read()
d=json.loads(raw)
for t in (d.get('data') or {}).get('activeTargets') or []:
    print(t.get('labels',{}).get('job'), t.get('health'), t.get('lastError','')[:120], t.get('scrapeUrl'))
" || docker exec prometheus python3 -c "
import urllib.request, json
d=json.loads(urllib.request.urlopen('http://127.0.0.1:9090/api/v1/targets', timeout=8).read().decode())
for t in (d.get('data') or {}).get('activeTargets') or []:
    print(t.get('labels',{}).get('job'), t.get('health'), (t.get('lastError') or '')[:120])
" || echo PROM_TARGETS_FAIL
echo "=== NODE EXPORTER? ==="
docker ps -a --format '{{.Names}}' | grep -i node || echo NO_NODE_EXPORTER
echo DIAG_DONE
"""


def main() -> int:
    c = connect()
    try:
        sudo_bash(c, REMOTE, timeout=60)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

