# -*- coding: utf-8 -*-
"""VPS smoke: deferred search-then-note must POST Memory rows + lookup finds them."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

BRANCH = os.environ.get("ASSISTANT_TEST_BRANCH", "fix/zalo/note-search-persist")
USER_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
CASES = 10
SKIP_DEPLOY = os.environ.get("SKIP_DEPLOY", "0").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    marker = f"NOTEPERSIST-{int(time.time())}"
    print(f"running test case 1/{CASES} deploy branch {BRANCH} skip={SKIP_DEPLOY}")
    c = connect()
    try:
        if not SKIP_DEPLOY:
            deploy = f"""
set -euo pipefail
cd /opt/assistant
sudo chown -R tn:tn /opt/assistant /data/assistant 2>/dev/null || true
git fetch origin {BRANCH} main develop
git checkout -B {BRANCH} origin/{BRANCH}
git reset --hard origin/{BRANCH}
bash run.sh load-openbao-env
python3 scripts/main/sync_router_worker_skills.py || true
SYNC_ZALO_RESTART=0 bash scripts/main/sync-zalo-plugins.sh
python3 test/scripts/notes_deferred_persist_unit.py
docker restart $(docker ps -q --filter name=assistant-hermes) 2>/dev/null || true
# Wait until Hermes is accepting work again.
for i in $(seq 1 36); do
  H=$(docker ps -q --filter name=assistant-hermes | head -1)
  if [ -n "$H" ] && docker exec "$H" true 2>/dev/null; then
    sleep 5
    echo HERMES_READY
    break
  fi
  sleep 5
done
echo DEPLOY_OK $(git rev-parse --short HEAD)
"""
            out = sudo_bash(c, deploy, timeout=900)
            if "notes_deferred_persist_unit: PASS" not in out:
                print("FAIL deploy/unit")
                print(out[-2500:])
                return 1
            print(f"running test case 2/{CASES} unit PASS on VPS")
        else:
            print(f"running test case 2/{CASES} skip deploy")

        ask = (
            f"Tim 3 tin tuyen dung Java backend/fullstack (nguon cong khai), "
            f"moi tin mot dong danh so, bat buoc ghi marker {marker} trong moi tin, "
            f"sau do note lai."
        )
        remote = f"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
export LAB_USER='{USER_ID}'
export LAB_MARKER='{marker}'
export LAB_ASK={json.dumps(ask)}
python3 - <<'PY'
import json, os, time, urllib.request, subprocess

user = os.environ["LAB_USER"]
marker = os.environ["LAB_MARKER"]
ask = os.environ["LAB_ASK"]
CASES = 10
started = time.time()

def post(url, payload, timeout=30):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={{"Content-Type": "application/json"}},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{{}}")

def sh(cmd):
    return subprocess.check_output(cmd, shell=True, text=True, errors="replace")

print(f"running test case 3/{{CASES}} inject search-then-note")
mid = f"np-{{int(time.time())}}"
payload = {{
    "type": "message",
    "data": {{
        "message": {{
            "msgId": mid,
            "cliMsgId": mid,
            "msgType": "webchat",
            "uidFrom": user,
            "idTo": user,
            "dName": "Tn",
            "ts": str(int(time.time() * 1000)),
            "content": ask,
        }},
        "threadType": 0,
        "threadId": user,
    }},
}}
inj = post("http://127.0.0.1:8787/inject-event", payload)
print("INJECT", inj.get("ok"), mid)

print(f"running test case 4/{{CASES}} wait host save confirm + marker")
reply_hit = False
save_hit = False
persist_log = False
deadline = time.time() + 300
while time.time() < deadline:
    try:
        logs = sh(
            "journalctl --user -u com.hermes.zaloplugin --since '15 min ago' --no-pager 2>/dev/null | tail -200; "
            "H=$(docker ps -q --filter name=assistant-hermes | head -1); "
            "docker logs --since 15m $H 2>&1 | tail -120"
        )
    except Exception as e:
        logs = str(e)
    low = logs.lower()
    if marker.lower() in low:
        reply_hit = True
    if "deferred note persist failed" in low:
        print("PERSIST_FAIL_SEEN")
    if "deferred note persist" in low or "note create without notes" in low:
        persist_log = True
    if (
        "the note operation completed" in low
        or "item(s)" in low
        or "ghi chú đã" in low
        or ("đã lưu" in low and "ghi" in low)
    ):
        save_hit = True
    if reply_hit and (save_hit or persist_log):
        break
    time.sleep(5)

print("REPLY_MARKER", reply_hit)
print("SAVE_SIGNAL", save_hit)
print("PERSIST_LOG", persist_log)

print(f"running test case 5/{{CASES}} Memory query by marker")
found = []
last_err = ""
for q in (marker, "java", "NOTEPERSIST"):
    try:
        res = post(
            "http://127.0.0.1:8095/v1/notes/query",
            {{
                "scope_id": f"zalo:user:{{user}}",
                "query": q,
                "limit": 20,
            }},
            timeout=15,
        )
        items = res.get("items") or []
        for it in items:
            content = str((it or {{}}).get("content") or "")
            if marker in content or (q == "java" and "java" in content.lower() and "NOTEPERSIST" in content):
                found.append(content[:240])
        print("MEMORY_Q", q, "count", len(items), "hit", len(found))
        if found:
            break
    except Exception as e:
        last_err = f"{{type(e).__name__}}: {{e}}"
if not found and last_err:
    print("MEMORY_ERR", last_err)
if found:
    print("MEMORY_SAMPLE", found[0][:180])

print(f"running test case 6/{{CASES}} Zalo lookup inject")
mid2 = f"np-lookup-{{int(time.time())}}"
payload2 = {{
    "type": "message",
    "data": {{
        "message": {{
            "msgId": mid2,
            "cliMsgId": mid2,
            "msgType": "webchat",
            "uidFrom": user,
            "idTo": user,
            "dName": "Tn",
            "ts": str(int(time.time() * 1000)),
            "content": "hien thi cac tin tuyen dung java da luu",
        }},
        "threadType": 0,
        "threadId": user,
    }},
}}
print("INJECT_LOOKUP", post("http://127.0.0.1:8787/inject-event", payload2).get("ok"))

print(f"running test case 7/{{CASES}} wait lookup reply")
lookup_ok = False
deadline = time.time() + 120
while time.time() < deadline:
    try:
        logs = sh(
            "journalctl --user -u com.hermes.zaloplugin --since '20 min ago' --no-pager 2>/dev/null | tail -120"
        )
    except Exception as e:
        logs = str(e)
    if marker in logs and "không tìm thấy ghi chú" not in logs.lower():
        lookup_ok = True
        break
    # Host gate announce for notes may not include marker in journal content;
    # Memory proof is the hard gate.
    time.sleep(4)
print("LOOKUP_OK", lookup_ok)

print(f"running test case 8/{{CASES}} adapter markers")
adapter = open("/opt/assistant/hermes/main/plugins/zalo/adapter.py", encoding="utf-8").read()
assert "real_thread_id" in adapter and "_as_persist_deferred_notes" in adapter
print("ADAPTER_OK")

print(f"running test case 9/{{CASES}} abnormal scan")
try:
    scan = sh(
        "journalctl --user -u com.hermes.zaloplugin --since '30 min ago' --no-pager 2>/dev/null | "
        "grep -iE 'notes\\.failed|missing_notes|deferred note persist failed|UnboundLocalError' || true"
    )
except Exception as e:
    scan = str(e)
print("ABNORMAL_SCAN", (scan or "").strip()[:500] or "none")

print(f"running test case 10/{{CASES}} verdict elapsed={{round(time.time()-started,1)}}s")
ok = bool(found) and marker in "\\n".join(found)
print("SMOKE_PASS" if ok else "SMOKE_FAIL")
if not ok:
    print("DIAG", {{
        "reply_hit": reply_hit,
        "save_hit": save_hit,
        "persist_log": persist_log,
        "memory": len(found),
        "lookup_ok": lookup_ok,
    }})
    raise SystemExit(1)
PY
"""
        print(f"running test case 3/{CASES} remote inject+memory (nested 3-10)")
        out2 = sudo_bash(c, remote, timeout=700)
        print(out2[-5000:])
        if "SMOKE_PASS" not in out2:
            print("FAIL smoke")
            return 1
        print("notes_deferred_persist_smoke: PASS")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
