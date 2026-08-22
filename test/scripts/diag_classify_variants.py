# -*- coding: utf-8 -*-
"""Compare classify: typo đặt lịch vs clean; inspect schedule DB fires."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash

REMOTE = r"""
set -euo pipefail
cd /opt/assistant
python3 <<'PY'
import json, urllib.request, sqlite3
from pathlib import Path

def classify(text):
    body=json.dumps({'text': text, 'timezone': 'Asia/Ho_Chi_Minh'}).encode()
    req=urllib.request.Request('http://127.0.0.1:8096/v1/classify', data=body, headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

variants=[
 ('clean', 'đặt lịch chạy một lần lúc 09:50 với nội dung chúc mọi người một buổi tối tốt lành bên gia đình, sau tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất kèm theo thông tin thời tiết Hồ Chí Minh hiện tại'),
 ('typo_missing_d', 'ặt lịch chạy một lần lúc 09:50 với nội dung chúc mọi người một buổi tối tốt lành bên gia đình, sau tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất kèm theo thông tin thời tiết Hồ Chí Minh hiện tại'),
 ('sau_as_now', 'đặt lịch chạy một lần lúc 09:50 với nội dung chúc mọi người một buổi tối tốt lành bên gia đình. Sau đó tìm giá xăng E5 RON92 và E10 RON95 mới nhất và thời tiết Hồ Chí Minh hiện tại'),
]
for name, text in variants:
    p=classify(text)
    print('===', name)
    print('hint=', p.get('task_hint'), 'cron=', p.get('cron_expr'), 'cadence=', p.get('cadence'), 'n=', len(p.get('instructions') or []))
    for i, ins in enumerate(p.get('instructions') or []):
        print(f'  [{i}]', str(ins)[:120])

# schedule DB
for db in (Path('/data/assistant/schedules.db'), Path('/opt/data/schedules.db'), Path('/data/schedules.db')):
    # find via docker
    pass
print('=== schedule list API ===')
try:
    with urllib.request.urlopen('http://127.0.0.1:8110/v1/schedules', timeout=10) as r:
        data=json.loads(r.read().decode() or '{}')
    rows=data.get('schedules') or []
    print('n_schedules', len(rows))
    for s in rows[-8:]:
        print('id=', s.get('id'), 'cron=', s.get('cron_expr'), 'enabled=', s.get('enabled'), 'next=', s.get('next_run_at'), 'fire=', str(s.get('fire_text') or '')[:160].replace('\n',' | '))
except Exception as e:
    print('sched_api_fail', e)

# docker exec schedule db
import subprocess
out=subprocess.check_output(['bash','-lc',"docker ps --format '{{.Names}}' | grep -i schedule | head -1"], text=True).strip()
print('schedule_container', out)
if out:
    try:
        sql=subprocess.check_output(['docker','exec',out,'sh','-lc',"sqlite3 /data/schedules.db \"SELECT id, cron_expr, enabled, next_run_at, substr(fire_text,1,120), last_run_at FROM schedules ORDER BY created_at DESC LIMIT 8;\" 2>/dev/null || sqlite3 /data/schedules.db '.tables'"], text=True, stderr=subprocess.STDOUT)
        print('sql', sql)
    except Exception as e:
        print('sql_fail', e)
        try:
            sql=subprocess.check_output(['docker','exec',out,'sh','-lc','ls -la /data; find /data -name \"*.db\" 2>/dev/null | head'], text=True)
            print(sql)
        except Exception as e2:
            print('ls_fail', e2)

# gateway lines with job instructions around 09:42-09:44
from pathlib import Path
for f in sorted(Path('/data/assistant/replicas').glob('*/logs/gateway.log'), key=lambda p:p.stat().st_mtime, reverse=True)[:2]:
    print('FILE', f)
    for ln in f.read_text(encoding='utf-8', errors='replace').splitlines():
        if '2026-08-22 09:42' in ln or '2026-08-22 09:43' in ln or '2026-08-22 09:44' in ln:
            print(ln[:420])
print('DIAG_CLASSIFY_VARIANTS_DONE')
PY
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=240)
    finally:
        c.close()
    Path("test/reports/diag-classify-variants.log").write_text(
        out or "", encoding="utf-8", errors="replace"
    )
    sys.stdout.buffer.write((out or "").encode("utf-8", errors="replace")[-16000:])
    sys.stdout.buffer.write(b"\n")
    return 0 if out and "DIAG_CLASSIFY_VARIANTS_DONE" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
