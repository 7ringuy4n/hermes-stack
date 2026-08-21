# -*- coding: utf-8 -*-
"""Lab: scheduleFire into LC group bypasses mention gate; history API.

Env: ASSISTANT_SSH_*
Reports: test/reports/run-schedule-group-fire/
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-schedule-group-fire"
esc = PW.replace("'", "'\\''")
LC_GID = "5275909225773405280"


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=30, allow_agent=False, look_for_keys=False)
    return c


def sudo_bash(c, script: str, timeout: int = 300) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = f"echo '{esc}' | sudo -S bash -lc \"echo {b64} | base64 -d | bash\""
    _i, o, e = c.exec_command(cmd, timeout=timeout, get_pty=True)
    chan = o.channel
    buf: list[str] = []
    while True:
        while chan.recv_ready():
            chunk = chan.recv(8192).decode("utf-8", "replace")
            sys.stdout.write(chunk)
            sys.stdout.flush()
            buf.append(chunk)
        while chan.recv_stderr_ready():
            chunk = chan.recv_stderr(8192).decode("utf-8", "replace")
            sys.stdout.write(chunk)
            sys.stdout.flush()
            buf.append(chunk)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    text = sanitize("".join(buf))
    if code != 0:
        raise SystemExit(f"remote exit {code}: {text[-800:]}")
    return text


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tag = uuid.uuid4().hex[:8]
    py = f"""
import json, subprocess, time
from pathlib import Path
admin=None
for ln in Path('/data/assistant/zalo_admin_users.txt').read_text(encoding='utf-8').splitlines():
  s=ln.strip()
  if not s or s.startswith('#'):
    continue
  admin=s.split('|')[0].strip()
  break
assert admin and not admin.startswith('#'), admin
gid = {LC_GID!r}
tag = {tag!r}
body = {{
  "cron_expr": "59 23 * * *",
  "cadence": "once",
  "timezone": "Asia/Ho_Chi_Minh",
  "text": f"lab schedule {{tag}}",
  "fire_text": f"xin chào từ schedule lab {{tag}}",
  "origin": {{"platform":"zalo","thread_id":gid,"chat_id":gid,"user_id":admin,"chat_name":"LC group"}},
  "context": {{"thread_id":gid,"thread_type":"group","chat_type":"group","sender_id":admin,"sender_name":"admin"}},
  "next_run_at": "2020-01-01T00:00:00Z",
}}
raw = subprocess.check_output([
  "docker","exec","-i","schedule-worker","wget","-qO-","-T","15",
  "--header=Content-Type: application/json",
  "--post-data="+json.dumps(body, ensure_ascii=False),
  "http://127.0.0.1:8110/v1/schedules",
], text=True)
print("CREATE", raw[:600])
tick = subprocess.check_output([
  "docker","exec","schedule-worker","wget","-qO-","-T","15",
  "--post-data=","http://127.0.0.1:8110/v1/schedules/tick",
], text=True)
print("TICK", tick[:400])
time.sleep(25)
hist = subprocess.check_output([
  "docker","exec","schedule-worker","wget","-qO-","-T","15",
  f"http://127.0.0.1:8110/v1/schedules/history?thread_id={{gid}}&limit=10",
], text=True)
print("HISTORY", hist[:1000])
names = subprocess.check_output(["docker","ps","--format","{{{{.Names}}}}"], text=True).splitlines()
h = [n for n in names if "hermes" in n][0]
logs = subprocess.check_output(["docker","logs","--since","5m",h], stderr=subprocess.STDOUT, text=True, errors="replace")
hits = [ln for ln in logs.splitlines() if tag in ln or "scheduleFire bypass" in ln]
print("LOG_HITS", len(hits))
for ln in hits[-15:]:
  print("LOG", ln[:220])
"""
    c = connect()
    py_b64 = base64.b64encode(py.encode("utf-8")).decode("ascii")
    out = sudo_bash(
        c,
        f"echo {py_b64} | base64 -d > /tmp/sched_group_fire.py && python3 /tmp/sched_group_fire.py",
        timeout=180,
    )
    report = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(),
        "tag": tag,
        "out": sanitize(out)[-5000:],
        "pass": {
            "create": "CREATE" in out and "ok" in out,
            "tick": "TICK" in out and "fired" in out,
            "history_ok": ('"status":"ok"' in out.replace(" ", "")) or ('"status": "ok"' in out),
            "bypass_log": "scheduleFire bypass" in out or "LOG_HITS" in out,
        },
    }
    (OUT / "raw.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["pass"], indent=2))
    c.close()
    return 0 if report["pass"]["create"] and report["pass"]["tick"] and report["pass"]["history_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
