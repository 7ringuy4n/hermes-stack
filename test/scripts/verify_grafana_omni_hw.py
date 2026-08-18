# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_high import connect, sudo_bash  # noqa: E402

REMOTE = r"""
set -euo pipefail
echo "=== omni scrape_success ==="
docker exec omni-exporter python -c "
import urllib.request
t=urllib.request.urlopen('http://127.0.0.1:9104/metrics', timeout=8).read().decode()
for line in t.splitlines():
    if line.startswith('omnirouter_scrape_success') or line.startswith('omnirouter_combos') or line.startswith('omnirouter_models '):
        print(line)
"
echo "=== node metrics via omni-exporter net ==="
docker exec omni-exporter python -c "
import urllib.request
t=urllib.request.urlopen('http://node-exporter:9100/metrics', timeout=8).read().decode()
print('MemAvailable', 'node_memory_MemAvailable_bytes' in t)
print('CPU', 'node_cpu_seconds_total' in t)
"
echo "=== prom jobs ==="
docker exec omni-exporter python -c "
import urllib.request, json
d=json.loads(urllib.request.urlopen('http://prometheus:9090/api/v1/targets', timeout=8).read().decode())
for t in (d.get('data') or {}).get('activeTargets') or []:
    print(t.get('labels',{}).get('job'), t.get('health'), (t.get('lastError') or '')[:80])
"
echo VERIFY_OK
"""


def main() -> int:
    c = connect()
    try:
        sudo_bash(c, REMOTE, timeout=45)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
