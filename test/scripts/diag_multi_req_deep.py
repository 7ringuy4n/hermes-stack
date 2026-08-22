# -*- coding: utf-8 -*-
"""Deep dig: classify + compound + schedule around user's mixed message."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash

REMOTE = r"""
set -euo pipefail
cd /opt/assistant
python3 <<'PY'
from pathlib import Path
import re
roots=[Path('/data/assistant/replicas'), Path('/opt/data/replicas')]
files=[]
for root in roots:
  if root.is_dir():
    files += list(root.glob('*/logs/gateway.log'))
    files += list(root.glob('*/logs/agent.log'))
files=sorted({f for f in files if f.is_file()}, key=lambda p: p.stat().st_mtime, reverse=True)[:6]
pat=re.compile(r'09:4[0-9]|09:5[0-5]|đặt lịch|dat lich|09:50|gia xăng|giá xăng|E5|E10|compound|schedule|workflow|job_|Yêu cầu|classify|instructions|fire|ack|send ok|response ready|inbound message|web_search|SearXNG|SOUL|deception|queue turn|parallel', re.I)
for f in files:
  print('====', f)
  lines=f.read_text(encoding='utf-8', errors='replace').splitlines()
  # prefer lines in morning window if timestamps present
  for ln in lines:
    if '2026-08-22 09:4' in ln or '2026-08-22 09:5' in ln or pat.search(ln):
      if '2026-08-22 09:4' in ln or '2026-08-22 09:5' in ln or any(k in ln.lower() for k in ['đặt lịch','dat lich','09:50','gia x','giá x','e5','e10','compound','schedule stored','workflow','yêu cầu','fire']):
        print(ln[:400])
  print('----')
PY
echo '=== schedule-worker logs ==='
docker logs --since 12h $(docker ps -q -f name=schedule | head -1) 2>&1 | tail -80 || true
echo '=== classify sample for user text ==='
python3 <<'PY'
import json, urllib.request
text='đặt lịch chạy một lần lúc 09:50 với nội dung chúc mọi người một buổi tối tốt lành bên gia đình, sau tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất kèm theo thông tin thời tiết Hồ Chí Minh hiện tại'
body=json.dumps({'text': text, 'timezone': 'Asia/Ho_Chi_Minh'}).encode()
req=urllib.request.Request('http://127.0.0.1:8096/v1/classify', data=body, headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=60) as r:
  raw=r.read().decode()
print(raw[:2000])
PY
echo DIAG_DEEP_DONE
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=180)
    finally:
        c.close()
    Path("test/reports/diag-multi-req-deep.log").write_text(
        out or "", encoding="utf-8", errors="replace"
    )
    sys.stdout.buffer.write((out or "").encode("utf-8", errors="replace")[-16000:])
    sys.stdout.buffer.write(b"\n")
    return 0 if out and "DIAG_DEEP_DONE" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
