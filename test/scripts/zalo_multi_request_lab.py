# -*- coding: utf-8 -*-
"""Lab: case 16 compound message â€” classify + Zalo-origin workflow (admin DM).

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Reports: test/reports/run-zalo-multi-request/ (no host/account)
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402
from sanitize import sanitize as _sanitize  # noqa: E402

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-multi-request"
WAIT_S = int(os.environ.get("ZALO_MULTI_WAIT_S", "720"))

FIXTURE = (
    "yêu cầu:\n"
    "1 vẽ hình thời tiết hiện tại ở thành phố hồ chi minh ở thời gian hiện tại, "
    "phải thấy rõ khung cảnh thành phố và gửi lên cho user\n"
    "2.Sau đó cập nhật giá xăng E5 RON92 và E5 RON95"
)


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    text = FIXTURE
    c = connect()
    try:
        print(f"[{ts()}] classify + zalo-origin workflow", flush=True)
        apply = sudo_bash(
            c,
            rf"""
set -euo pipefail
cd /opt/assistant
python3 - <<'PY'
import json, urllib.request
from pathlib import Path
text = {text!r}

def post(url, body, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(), method="POST", headers={{"Content-Type":"application/json"}})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{{}}")

t0 = __import__("time").time()
plan = {{}}
for _try in range(3):
    plan = post("http://127.0.0.1:8096/v1/classify", {{"text": text, "timezone": "Asia/Ho_Chi_Minh"}}, 35)
    inst = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
    if plan.get("ok") and len(inst) >= 2:
        break
    __import__("time").sleep(2)
ms = int((__import__("time").time() - t0) * 1000)
print("CLASSIFY", plan.get("task_hint"), "n", len(inst), "exec", plan.get("execution_class"), "ms", ms, "ok", plan.get("ok"), "err", plan.get("error"))
if len(inst) < 2:
    raise SystemExit("NEED_TWO_INSTRUCTIONS")
admin_id = ""
for path in ("/data/assistant/zalo_admin_users.txt", "/opt/data/zalo_admin_users.txt"):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        continue
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        tid = raw.partition("|")[0].strip()
        if tid:
            admin_id = tid
            break
    if admin_id:
        break
if not admin_id:
    raise SystemExit("NO_ADMIN_DM")
got = post("http://127.0.0.1:8108/v1/workflows", {{
    "instructions": inst,
    "sequential": True,
    "wrap": True,
    "origin": {{"platform": "zalo", "thread_id": admin_id, "thread_type": "user", "user_id": admin_id, "chat_id": admin_id, "test": "case16"}},
    "context": {{"thread_id": admin_id, "thread_type": "user", "chat_type": "dm", "sender_id": admin_id, "execute": "hermes", "plan": plan}},
}}, 30)
wf = got.get("workflow") or {{}}
jobs = wf.get("jobs") if isinstance(wf.get("jobs"), list) else []
print("WF", got.get("ok"), wf.get("id"), "JOBS", len(jobs))
if not got.get("ok") or len(jobs) < 2:
    raise SystemExit("BAD_WF")
print("WF_ID=" + str(wf.get("id") or ""))
print("CREATE_DONE")
PY
echo CREATE_OK
""",
            timeout=240,
        )
        print(_sanitize(apply[-2000:]), flush=True)
        if "NEED_TWO_INSTRUCTIONS" in apply or "CREATE_OK" not in apply:
            print("FAIL classify/create", flush=True)
            return 1
        wid = ""
        for line in apply.splitlines():
            if line.startswith("WF_ID="):
                wid = line.split("=", 1)[1].strip()
        if not wid:
            print("FAIL missing WF_ID", flush=True)
            return 1
        since = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[{ts()}] watch workflow {wid} up to {WAIT_S}s", flush=True)
        watch = sudo_bash(
            c,
            rf"""
set +e
deadline=$(( $(date +%s) + {WAIT_S} ))
since="{since}"
wid="{wid}"
while [ "$(date +%s)" -lt "$deadline" ]; do
  curl -sS -m 5 http://127.0.0.1:8787/health | python3 -c 'import sys,json; d=json.load(sys.stdin); print("plugin loggedIn", d.get("loggedIn"), "sse", d.get("sseClients"))' || echo plugin_down
  py=$(curl -sS -m 8 "http://127.0.0.1:8108/v1/workflows/$wid")
  echo "$py" | python3 -c 'import sys,json
d=json.load(sys.stdin)
wf=d.get("workflow") or {{}}
jobs=wf.get("jobs") if isinstance(wf.get("jobs"), list) else []
st=[str(j.get("status") or "") for j in jobs]
print("wf", wf.get("status"), "jobs", ",".join(st), "n", len(jobs))
okn=sum(1 for s in st if s=="COMPLETED")
if okn>=2:
    print("TWO_DONE")
'
  logs=$(docker ps --filter name=hermes --format '{{{{.Names}}}}' | while read n; do docker logs --since "$since" "$n" 2>&1; done)
  echo "$logs" | grep -E 'send-attachment path|workflow job done|\[zalo\] send ' | tail -6
  echo "$py" | python3 -c 'import sys,json
d=json.load(sys.stdin)
wf=d.get("workflow") or {{}}
jobs=wf.get("jobs") if isinstance(wf.get("jobs"), list) else []
st=[str(j.get("status") or "") for j in jobs]
raise SystemExit(0 if sum(1 for s in st if s=="COMPLETED")>=2 else 1)
' && echo TWO_DONE && break
  sleep 12
done
echo WATCH_DONE
""",
            timeout=WAIT_S + 60,
        )
        print(_sanitize(watch[-2500:]), flush=True)
        (OUT / "watch.txt").write_text(_sanitize(watch), encoding="utf-8")
        ok = "TWO_DONE" in watch
        print("CASE16 PASS" if ok else "CASE16 FAIL", flush=True)
        return 0 if ok else 1
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

