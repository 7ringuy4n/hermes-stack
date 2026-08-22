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

REMOTE = r"""
set -euo pipefail
cd /opt/assistant
python3 <<'PY'
import json, time, urllib.request, re
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

want = __WANT_NAME__
wait_s = __WAIT_S__
tz = ZoneInfo("Asia/Ho_Chi_Minh")
fire_at = (datetime.now(tz) + timedelta(hours=2)).replace(second=0, microsecond=0)
hhmm = fire_at.strftime("%H:%M")
tag = "mixedsched-%d" % int(time.time())
text = (
    "đặt lịch chạy một lần lúc %s với nội dung chúc mọi người một buổi tối tốt lành bên gia đình, "
    "sau tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất kèm theo thông tin thời tiết Hồ Chí Minh hiện tại "
    "[%s]"
) % (hhmm, tag)

def find_uid():
    roots = []
    for base in (Path("/data/assistant"), Path("/opt/data")):
        if base.is_dir():
            roots.extend(base.rglob("*allow*"))
    for p in roots:
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        def walk(o):
            if isinstance(o, dict):
                name = str(o.get("name") or o.get("displayName") or "")
                if name == want:
                    return str(o.get("id") or o.get("userId") or "")
                for v in o.values():
                    r = walk(v)
                    if r:
                        return r
            if isinstance(o, list):
                for i in o:
                    r = walk(i)
                    if r:
                        return r
            return ""
        uid = walk(data)
        if uid:
            return uid
    return ""

uid = find_uid()
print("uid_len", len(uid), "hhmm", hhmm, "tag", tag)
assert uid, "missing Tn id"
offs = {}
for root in (Path("/data/assistant/replicas"), Path("/opt/data/replicas")):
    if not root.is_dir():
        continue
    for f in root.glob("*/logs/gateway.log"):
        offs[str(f)] = f.stat().st_size
body = {
    "type": "message",
    "threadId": uid,
    "threadType": "user",
    "senderId": uid,
    "senderName": want,
    "text": text,
}
req = urllib.request.Request(
    "http://127.0.0.1:8787/inject-event",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as r:
    print("inject", r.status, r.read()[:120])
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
summary = {
    "tag": tag,
    "hhmm": hhmm,
    "schedule_stored": stored,
    "workflow_multi": wf,
    "send_ok": send_ok,
    "soul_blocked": soul,
    "pass": bool(stored and (not wf) and (not soul)),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("PASS_MIXED" if summary["pass"] else "FAIL_MIXED")
PY
""".replace("__WANT_NAME__", repr(WANT_NAME)).replace("__WAIT_S__", str(WAIT_S))


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
