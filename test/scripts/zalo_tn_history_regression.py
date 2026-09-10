# -*- coding: utf-8 -*-
"""Tn HISTORY regression pack — one inject per known production gap class.

Runs sequentially; exits non-zero on first FAIL_* so the operator can fix and
retry only the failed case (set ZALO_HISTORY_CASE=<name>).

Cases (default all):
  greeting      — short DM gets outbound (SOUL/combo no-reply class)
  schedule      — đặt lịch lúc HH:MM stores cron (classify JSON once_at)
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
import json, time, urllib.request, os, re, subprocess
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

want_name = {want!r}
wait_s = {wait}
case = {case!r}
tag = "hist-%s-%d" % (case, int(time.time()))

uid = uname = ""
first_uid = first_name = ""
for path in ("/data/assistant/zalo_admin_users.txt", "/opt/data/zalo_admin_users.txt"):
    p = Path(path)
    if not p.is_file():
        continue
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        left, _, right = raw.partition("|")
        if not left.strip():
            continue
        if not first_uid:
            first_uid, first_name = left.strip(), right.strip() or "admin"
        if right.strip().lower() == want_name.lower():
            uid, uname = left.strip(), right.strip()
            break
    if uid:
        break
if not uid:
    # main: any admin; develop suites set ZALO_REQUIRE_NAMED_ADMIN=1 (default)
    _strict = (os.environ.get("ZALO_REQUIRE_NAMED_ADMIN") or "1").strip().lower() in ("1", "true", "yes")
    if _strict or not first_uid:
        raise SystemExit("NO_ADMIN_USER")
    uid, uname = first_uid, first_name

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
        "messageId": tag,
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

zalo = subprocess.check_output(
    ["docker", "ps", "-q", "--filter", "label=com.docker.compose.service=zalo-api"],
    text=True,
).split()[0]
probe = r'''import json, os, psycopg
with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
 row=conn.execute(
  "SELECT content, meta FROM zalo_message_history "
  "WHERE thread_id=%s AND thread_type='user' AND event='delivered' "
  "AND meta->>'source_message_id'=%s AND created_at>=to_timestamp(%s) "
  "ORDER BY id DESC LIMIT 1",
  (os.environ['LAB_THREAD'],os.environ['LAB_SOURCE'],float(os.environ['LAB_STARTED']))
 ).fetchone()
print(json.dumps({{'content':row[0],'meta':row[1]}} if row else {{}}))'''
started = time.time() - 3

def delivered():
    raw = subprocess.check_output([
        "docker", "exec", "-e", "LAB_THREAD=" + uid,
        "-e", "LAB_SOURCE=" + tag, "-e", "LAB_STARTED=" + repr(started),
        zalo, "python3", "-c", probe,
    ], text=True, errors="replace")
    return json.loads(raw or "{{}}")

def schedules():
    with urllib.request.urlopen("http://127.0.0.1:8110/v1/schedules", timeout=15) as r:
        body=json.loads(r.read() or b'{{}}')
    rows=body.get('schedules') if isinstance(body,dict) else body
    return rows if isinstance(rows,list) else []

def tagged_schedules():
    return [row for row in schedules() if tag in json.dumps(row,ensure_ascii=False)]

def cleanup():
    for row in tagged_schedules():
        sid=str(row.get('id') or '') if isinstance(row,dict) else ''
        if not re.fullmatch(r'[A-Za-z0-9_-]+',sid):
            continue
        delete=urllib.request.Request(
            "http://127.0.0.1:8110/v1/schedules/" + sid, method="DELETE"
        )
        try:
            urllib.request.urlopen(delete,timeout=15).read()
        except Exception:
            pass

deadline = time.time() + wait_s
failure = "timeout"
try:
    while time.time() < deadline:
        result=delivered()
        meta=result.get('meta') if isinstance(result.get('meta'),dict) else {{}}
        rows=tagged_schedules() if case in ("schedule","mixed_store") else []
        if case in ("greeting", "multilang"):
            if str(result.get('content') or '').strip() and meta.get('delivery_kind') in (None,'result','queue_recovery'):
                print("PASS_HIST", case)
                raise SystemExit(0)
        elif case in ("schedule", "mixed_store"):
            if meta.get('delivery_kind') == 'gate' and len(rows) == 1:
                print("PASS_HIST", case)
                raise SystemExit(0)
            failure="gate=%s tagged_schedules=%d" % (meta.get('delivery_kind')=='gate',len(rows))
        elif case == "pdf_shortcut":
            name=str(meta.get('file_name') or '')
            if meta.get('attachment_kind') == 'document' and name.lower().endswith('.pdf'):
                print("PASS_HIST", case)
                raise SystemExit(0)
            failure="document=%s pdf=%s" % (meta.get('attachment_kind')=='document',name.lower().endswith('.pdf'))
        time.sleep(2)
finally:
    cleanup()
    if case in ("schedule","mixed_store") and tagged_schedules():
        print("FAIL_HIST",case,"schedule_cleanup")
        raise SystemExit(2)
print("FAIL_HIST", case, failure)
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
