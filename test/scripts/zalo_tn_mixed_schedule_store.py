# -*- coding: utf-8 -*-
"""Tn inject: mixed đặt-lịch greeting+fuel+weather must STORE schedule, not fire 3 jobs now."""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

WANT_NAME = (os.environ.get("ZALO_TEST_USER_NAME") or "Tn").strip()
WAIT_S = int(os.environ.get("ZALO_CASE_WAIT_S") or "90")

REMOTE = rf"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, time, urllib.request, os, re
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

want_name = {WANT_NAME!r}
wait_s = {WAIT_S}
tz = ZoneInfo("Asia/Ho_Chi_Minh")
fire_at = (datetime.now(tz) + timedelta(hours=2)).replace(second=0, microsecond=0)
hhmm = fire_at.strftime("%H:%M")
tag = "mixedsched-%d" % int(time.time())
text = (
    "đặt lịch chạy một lần lúc %s với nội dung chúc mọi người một buổi tối tốt lành bên gia đình, "
    "sau tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất kèm theo thông tin thời tiết Hồ Chí Minh hiện tại "
    "[%s]"
) % (hhmm, tag)

uid = ""
uname = ""
for path in (
    "/data/assistant/zalo_admin_users.txt",
    "/opt/data/zalo_admin_users.txt",
):
    p = Path(path)
    if not p.is_file():
        continue
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        left, sep, right = raw.partition("|")
        cand = left.strip()
        name = right.strip()
        if not cand:
            continue
        if want_name and name.lower() == want_name.lower():
            uid, uname = cand, name
            break
        if not uid:
            uid, uname = cand, name or "admin"
    if uid and want_name and uname.lower() == want_name.lower():
        break
if not uid:
    raise SystemExit("NO_ADMIN_USER")
print("USER_NAME", uname, "hhmm", hhmm, "tag", tag)

offs = {{}}
for root in ("/data/assistant/replicas", "/opt/data/replicas"):
    base = Path(root)
    if not base.is_dir():
        continue
    for f in base.glob("*/logs/gateway.log"):
        offs[str(f)] = f.stat().st_size

tok = (os.environ.get("ZALO_PLUGIN_TOKEN") or "").strip()
headers = {{"Content-Type": "application/json"}}
if tok:
    headers["Authorization"] = "Bearer " + tok
payload = {{
    "type": "message",
    "payload": {{
        "threadId": uid,
        "threadType": "user",
        "senderId": uid,
        "senderName": uname,
        "text": text,
        "isSelf": False,
    }},
}}
req = urllib.request.Request(
    "http://127.0.0.1:8787/inject-event",
    data=json.dumps(payload).encode(),
    headers=headers,
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as r:
    print("inject", r.status, r.read()[:160])

time.sleep(wait_s)
chunks = []
for path, off in offs.items():
    p = Path(path)
    if p.is_file():
        chunks.append(p.read_bytes()[int(off):].decode("utf-8", errors="replace"))
blob = "\n".join(chunks)
print(blob[-5000:])
stored = bool(re.search(r"schedule stored|Đã lưu lịch|Da luu lich", blob, re.I))
wf = bool(re.search(r"workflow created jobs=\s*[2-9]", blob, re.I))
soul = bool(re.search(r"deception_hide|SOUL.md blocked", blob, re.I))
send_ok = len(re.findall(r"send ok", blob, re.I))
summary = {{
    "tag": tag,
    "hhmm": hhmm,
    "schedule_stored": stored,
    "workflow_multi": wf,
    "send_ok": send_ok,
    "soul_blocked": soul,
    "pass": bool(stored and (not wf) and (not soul)),
}}
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("PASS_MIXED" if summary["pass"] else "FAIL_MIXED")
PY
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=WAIT_S + 120)
    finally:
        c.close()
    Path("test/reports/run-zalo-tn-mixed-schedule-store.log").write_text(
        out or "", encoding="utf-8", errors="replace"
    )
    print(out[-8000:] if out else "")
    return 0 if out and "PASS_MIXED" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
