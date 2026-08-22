# -*- coding: utf-8 -*-
"""Tn HISTORY regression pack — one inject per known production gap class.

Runs sequentially; exits non-zero on first FAIL_* so the operator can fix and
retry only the failed case (set ZALO_HISTORY_CASE=<name>).

Cases (default all):
  greeting      — short DM gets outbound (SOUL/combo no-reply class)
  schedule      — đặt lịch lúc HH:MM stores cron (503/heuristic class)
  mixed_store   — schedule+fuel+weather stores one lịch (async demote class)
  pdf_shortcut  — tạo 1 file pdf… routes via office-file / no fake send claim
  multilang     — English short greeting still replies (SOUL multi-lang)

Env: ASSISTANT_SSH_*, ZALO_TEST_USER_NAME=Tn, ZALO_HISTORY_CASE, ZALO_CASE_WAIT_S
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

WANT = (os.environ.get("ZALO_TEST_USER_NAME") or "Tn").strip()
WAIT = int(os.environ.get("ZALO_CASE_WAIT_S") or "120")
ONLY = (os.environ.get("ZALO_HISTORY_CASE") or "").strip().lower()

CASES = {
    "greeting": "chào buổi sáng lịch sử regression",
    "schedule": None,  # built remotely with HH:MM
    "mixed_store": None,
    "pdf_shortcut": "tạo 1 file pdf chứa số 7 gửi cho tôi",
    "multilang": "Good morning — please reply briefly in English.",
}


REMOTE_TMPL = r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, time, urllib.request, os, re
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

want_name = {want!r}
wait_s = {wait}
case = {case!r}
tag = "hist-%s-%d" % (case, int(time.time()))

uid = uname = ""
for path in ("/data/assistant/zalo_admin_users.txt", "/opt/data/zalo_admin_users.txt"):
    p = Path(path)
    if not p.is_file():
        continue
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        left, _, right = raw.partition("|")
        if right.strip().lower() == want_name.lower():
            uid, uname = left.strip(), right.strip()
            break
    if uid:
        break
if not uid:
    raise SystemExit("NO_ADMIN_USER")

tz = ZoneInfo("Asia/Ho_Chi_Minh")
hhmm = (datetime.now(tz) + timedelta(hours=3)).strftime("%H:%M")
texts = {{
    "greeting": "chào buổi sáng lịch sử regression [" + tag + "]",
    "schedule": "đặt lịch lúc %s nhắc uống nước [%s]" % (hhmm, tag),
    "mixed_store": (
        "đặt lịch lúc %s chào mọi người, sau giá xăng E5 và thời tiết Hà Nội [%s]"
        % (hhmm, tag)
    ),
    "pdf_shortcut": "tạo 1 file pdf chứa số 7 gửi cho tôi [" + tag + "]",
    "multilang": "Good morning — please reply briefly in English. [" + tag + "]",
}}
text = texts[case]

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
    print("INJECT", r.status, case, tag)

deadline = time.time() + wait_s
chunk = ""
while time.time() < deadline:
    chunk = ""
    for path, off in list(offs.items()):
        p = Path(path)
        if not p.is_file():
            continue
        data = p.read_bytes()[off:]
        chunk += data.decode("utf-8", "replace")
        offs[path] = p.stat().st_size
    low = chunk.lower()
    if case in ("greeting", "multilang"):
        if "send ok" in low or "outbound" in low:
            print("PASS_HIST", case)
            raise SystemExit(0)
    elif case in ("schedule", "mixed_store"):
        # schedule ack or cron write — not 3 immediate weather jobs
        if "schedule" in low or "cron" in low or "đặt lịch" in chunk.lower() or "lich" in low:
            if case == "mixed_store" and low.count("thời tiết") + low.count("weather") > 2:
                # duplicate weather smell — keep waiting for clearer signal
                pass
            else:
                print("PASS_HIST", case)
                raise SystemExit(0)
    elif case == "pdf_shortcut":
        if "office-file" in low or "send" in low and "pdf" in low:
            if "reportlab" in low or "skill_view" in low and "pip" in low:
                print("FAIL_HIST", case, "pdf_skill_collision_smell")
                raise SystemExit(2)
            print("PASS_HIST", case)
            raise SystemExit(0)
    time.sleep(2)
print("FAIL_HIST", case, "timeout")
print(chunk[-2000:])
raise SystemExit(1)
PY
"""


def run_case(name: str) -> int:
    print(f"==> history case {name}", flush=True)
    remote = REMOTE_TMPL.format(want=WANT, wait=WAIT, case=name)
    c = connect()
    try:
        out = sudo_bash(c, remote)
        print(out)
        return 0 if out and f"PASS_HIST {name}" in out else 1
    finally:
        c.close()


def main() -> int:
    names = [ONLY] if ONLY else list(CASES.keys())
    for name in names:
        if name not in CASES:
            print(f"unknown case {name}", file=sys.stderr)
            return 2
        rc = run_case(name)
        if rc != 0:
            print(f"STOP on failed case={name} rc={rc} — fix then: ZALO_HISTORY_CASE={name}")
            return rc
    print("PASS_HIST_ALL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
