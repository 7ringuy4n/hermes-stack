# -*- coding: utf-8 -*-
"""Diagnose Tn multi-request: schedule + fuel + weather duplicate/missing parts."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash

REMOTE = r"""
set -euo pipefail
cd /opt/assistant
echo '=== HEAD ==='
git log -1 --oneline
echo '=== hermes/router/omni/zalo status ==='
docker ps --format '{{.Names}} {{.Status}}' | grep -iE 'hermes|router|omni|zalo' || true
echo '=== recent gateway.log hits (multi/fuel/weather/schedule) ==='
python3 <<'PY'
from pathlib import Path
import re
roots=[Path('/data/assistant/replicas'), Path('/opt/data/replicas')]
keys=re.compile(r'gia xang|E5|E10|RON|thoi tiet|thời tiết|Hồ Chí Minh|Ho Chi Minh|dat lich|đặt lịch|09:50|schedule|classifier|multi|compound|queue turn|SOUL|deception|send ok|response ready|inbound message|web_search|fuel|xăng', re.I)
files=[]
for root in roots:
    if not root.is_dir():
        continue
    files.extend(sorted(root.glob('*/logs/gateway.log'), key=lambda p: p.stat().st_mtime, reverse=True)[:3])
    files.extend(sorted(root.glob('*/logs/agent.log'), key=lambda p: p.stat().st_mtime, reverse=True)[:2])
seen=set()
for f in files:
    if f in seen or not f.is_file():
        continue
    seen.add(f)
    print('FILE', f, 'mtime', f.stat().st_mtime)
    try:
        lines=f.read_text(encoding='utf-8', errors='replace').splitlines()
    except Exception as e:
        print(' read_fail', e); continue
    # last 400 matching lines from end window
    window=lines[-2500:]
    hits=[ln for ln in window if keys.search(ln)]
    for ln in hits[-80:]:
        print(ln[:320])
    print('---')
PY
echo '=== docker hermes logs (tail) ==='
docker logs --since 6h $(docker ps -q -f name=assistant-hermes | head -1) 2>&1 | grep -iE 'schedule|classif|multi|weather|xang|fuel|compound|queue turn|SOUL|deception|send ok|response ready|inbound' | tail -60 || true
echo '=== router-worker search logs ==='
docker logs --since 6h router-worker 2>&1 | grep -iE 'search|tavily|searx|gia|xang|weather|thoi|classify|schedule' | tail -40 || true
echo '=== omni search/routing ==='
docker logs --since 6h omni-router 2>&1 | grep -iE 'SEARCH|tavily|searx|gia|weather|xang' | tail -30 || true
echo '=== zalo journal ==='
journalctl --user -u com.hermes.zaloplugin --since '6 hours ago' --no-pager 2>/dev/null | grep -iE 'inject|send|error|fail|schedule|09:50|xang|weather|thoi' | tail -40 || true
echo DIAG_MULTI_REQ_DONE
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=180)
    finally:
        c.close()
    Path("test/reports/diag-multi-req-fuel-weather.log").write_text(
        out or "", encoding="utf-8", errors="replace"
    )
    sys.stdout.buffer.write((out or "").encode("utf-8", errors="replace")[-14000:])
    sys.stdout.buffer.write(b"\n")
    return 0 if out and "DIAG_MULTI_REQ_DONE" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
