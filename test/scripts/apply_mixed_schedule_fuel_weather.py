# -*- coding: utf-8 -*-
"""Pull develop, rebuild router-worker+workflow, sync zalo multi_request, verify classify schedule force."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash

REMOTE = r"""
set -euo pipefail
cd /opt/assistant
git fetch origin
git checkout develop
git reset --hard origin/develop
echo HEAD=$(git log -1 --oneline)

docker compose --project-directory /opt/assistant -f docker/docker-compose.yml \
  build router-worker workflow 2>&1 | tail -50
docker compose --project-directory /opt/assistant -f docker/docker-compose.yml \
  up -d --force-recreate router-worker workflow hermes 2>&1 | tail -40
sleep 18

# Sync zalo plugin replicas (multi_request wrap)
python3 <<'PY'
from pathlib import Path
import shutil
src = Path('/opt/assistant/hermes/main/plugins/zalo/multi_request.py')
for root in (Path('/opt/data/replicas'), Path('/data/assistant/replicas')):
    if not root.is_dir():
        continue
    for dest in root.glob('*/plugins/zalo/multi_request.py'):
        shutil.copy2(src, dest)
        print('synced', dest)
# shared plugins tree
for shared in (Path('/opt/data/plugins/zalo'), Path('/data/assistant/plugins/zalo')):
    if shared.is_dir():
        shutil.copy2(src, shared / 'multi_request.py')
        print('synced shared', shared / 'multi_request.py')
PY

# SOUL deception_hide scan
python3 <<'PY'
from pathlib import Path
import re
pat=re.compile(r'do\s+not.{0,40}tell.{0,40}user', re.I)
soul=Path('/opt/assistant/hermes/main/SOUL.md').read_text(encoding='utf-8', errors='replace')
print('soul_deception_hide_hits', len(pat.findall(soul)))
for dest_root in (Path('/opt/data'), Path('/data/assistant')):
    d=dest_root/'SOUL.md'
    if d.parent.is_dir():
        d.write_text(soul, encoding='utf-8')
        print('soul_copied', d)
PY

python3 <<'PY'
import json, urllib.request
text='ặt lịch chạy một lần lúc 09:50 với nội dung chúc mọi người một buổi tối tốt lành bên gia đình, sau tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất kèm theo thông tin thời tiết Hồ Chí Minh hiện tại'
# also force demotion path via normalize by posting
body=json.dumps({'text': text, 'timezone': 'Asia/Ho_Chi_Minh'}).encode()
req=urllib.request.Request('http://127.0.0.1:8096/v1/classify', data=body, headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=60) as r:
    p=json.loads(r.read().decode())
print('hint', p.get('task_hint'), 'cron', p.get('cron_expr'), 'n', len(p.get('instructions') or []))
assert p.get('task_hint')=='schedule', p
assert p.get('cron_expr') in ('50 9 * * *', '50 09 * * *'), p
assert len(p.get('instructions') or [])>=3, p
print('CLASSIFY_SCHEDULE_OK')
PY

docker ps --filter name=router-worker --format '{{.Names}} {{.Status}}'
docker ps --filter name=workflow --format '{{.Names}} {{.Status}}'
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
echo OK_APPLY_MIXED_SCHEDULE
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=1200)
    finally:
        c.close()
    Path("test/reports/apply-mixed-schedule-fuel-weather.log").write_text(
        out or "", encoding="utf-8", errors="replace"
    )
    sys.stdout.buffer.write((out or "").encode("utf-8", errors="replace")[-14000:])
    sys.stdout.buffer.write(b"\n")
    return 0 if out and "OK_APPLY_MIXED_SCHEDULE" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
