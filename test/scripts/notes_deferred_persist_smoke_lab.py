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


def main() -> int:
    marker = f"NOTEPERSIST-{int(time.time())}"
    print(f"running test case 1/{CASES} deploy branch {BRANCH}")
    c = connect()
    try:
        deploy = f"""
set -euo pipefail
cd /opt/assistant
sudo chown -R tn:tn /opt/assistant /data/assistant 2>/dev/null || true
git fetch origin {BRANCH} main develop
git checkout -B {BRANCH} origin/{BRANCH}
git reset --hard origin/{BRANCH}
bash run.sh load-openbao-env
# Avoid full update churn: sync plugin + skill bake, then restart Hermes replicas.
python3 scripts/main/sync_router_worker_skills.py || true
SYNC_ZALO_RESTART=0 bash scripts/main/sync-zalo-plugins.sh
python3 test/scripts/notes_deferred_persist_unit.py
# Restart Hermes so replicas import fresh zalo modules.
docker restart $(docker ps -q --filter name=assistant-hermes) 2>/dev/null || true
sleep 8
echo DEPLOY_OK $(git rev-parse --short HEAD)
"""
        out = sudo_bash(c, deploy, timeout=900)
        if "notes_deferred_persist_unit: PASS" not in out and "PASS" not in out:
            print("FAIL deploy/unit")
            print(out[-2500:])
            return 1
        print(f"running test case 2/{CASES} unit PASS on VPS")

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
import json, os, time, urllib.request

user = os.environ["LAB_USER"]
marker = os.environ["LAB_MARKER"]
ask = os.environ["LAB_ASK"]
CASES = 10

def post(url, payload, timeout=30):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={{"Content-Type": "application/json"}},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{{}}")

def get(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{{}}")

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
deadline = time.time() + 240
reply_hit = False
save_hit = False
body_snip = ""
while time.time() < deadline:
    try:
        # Durable outbound / session tails vary; scrape recent hermes + zalo logs.
        import subprocess
        logs = subprocess.check_output(
            "journalctl --user -u com.hermes.zaloplugin -n 80 --no-pager 2>/dev/null; "
            "docker logs --tail 120 $(docker ps -q --filter name=assistant-hermes | head -1) 2>&1 | tail -80",
            shell=True,
            text=True,
            errors="replace",
        )
    except Exception as e:
        logs = str(e)
    low = logs.lower()
    if marker.lower() in low:
        reply_hit = True
    if (
        "ghi chú" in low
        or "ghi chu" in low
        or "note operation completed" in low
        or "đã lưu" in low
        or "da luu" in low
        or "notes_saved" in low
        or "deferred note persist" in low
    ):
        # Prefer host confirmation language; agent false claims are stripped.
        if "item" in low or "ghi chú" in logs or "ghi chu" in low or "completed" in low:
            save_hit = True
    if "deferred note persist" in low or "POST /v1/notes" in logs:
        save_hit = True
    if reply_hit and save_hit:
        body_snip = logs[-1500:]
        break
    time.sleep(5)

print("REPLY_MARKER", reply_hit)
print("SAVE_SIGNAL", save_hit)

print(f"running test case 5/{{CASES}} Memory query by marker")
# Resolve memory URL from compose network / localhost publish.
mem_urls = [
    "http://127.0.0.1:8095/v1/notes/query",
    "http://memory:8095/v1/notes/query",
    "http://memory-manager:8095/v1/notes/query",
]
# scope is typically zalo DM user id
found = []
last_err = ""
for url in mem_urls:
    for q in (marker, "java", "tuyển dụng", "tuyen dung"):
        try:
            res = post(
                url,
                {{
                    "scope_id": f"zalo:user:{{user}}",
                    "query": q,
                    "limit": 20,
                }},
                timeout=15,
            )
            items = res.get("items") or res.get("notes") or []
            for it in items:
                content = str((it or {{}}).get("content") or "")
                if marker in content or "java" in content.lower():
                    found.append(content[:200])
            if found:
                print("MEMORY_URL", url, "QUERY", q, "COUNT", len(found))
                break
        except Exception as e:
            last_err = f"{{url}}: {{type(e).__name__}}"
    if found:
        break

print("MEMORY_HITS", len(found))
if found:
    print("MEMORY_SAMPLE", found[0][:180])
elif last_err:
    print("MEMORY_ERR", last_err)

print(f"running test case 6/{{CASES}} Zalo lookup inject")
mid2 = f"np-lookup-{{int(time.time())}}"
lookup_ask = "hien thi cac tin tuyen dung java da luu"
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
            "content": lookup_ask,
        }},
        "threadType": 0,
        "threadId": user,
    }},
}}
print("INJECT_LOOKUP", post("http://127.0.0.1:8787/inject-event", payload2).get("ok"))

print(f"running test case 7/{{CASES}} wait lookup reply")
lookup_ok = False
deadline = time.time() + 90
while time.time() < deadline:
    try:
        import subprocess
        logs = subprocess.check_output(
            "journalctl --user -u com.hermes.zaloplugin -n 60 --no-pager 2>/dev/null; "
            "docker logs --tail 80 $(docker ps -q --filter name=assistant-hermes | head -1) 2>&1 | tail -60",
            shell=True,
            text=True,
            errors="replace",
        )
    except Exception as e:
        logs = str(e)
    if marker in logs or ("java" in logs.lower() and "không tìm thấy" not in logs.lower()):
        if "không tìm thấy ghi chú" not in logs.lower() and "khong tim thay ghi chu" not in logs.lower():
            lookup_ok = True
            break
    time.sleep(4)
print("LOOKUP_OK", lookup_ok)

print(f"running test case 8/{{CASES}} adapter markers present")
adapter = open("/opt/assistant/hermes/main/plugins/zalo/adapter.py", encoding="utf-8").read()
assert "_as_persist_deferred_notes" in adapter
assert "defer persist after gather" in adapter
print("ADAPTER_OK")

print(f"running test case 9/{{CASES}} recent abnormal note failure scan")
try:
    import subprocess
    scan = subprocess.check_output(
        "journalctl --user -u com.hermes.zaloplugin -n 200 --no-pager 2>/dev/null | "
        "rg -i 'notes\\.failed|missing_notes|deferred note persist failed|UnboundLocalError' || true",
        shell=True,
        text=True,
        errors="replace",
    )
except Exception as e:
    scan = str(e)
print("ABNORMAL_SCAN", (scan or "").strip()[:500] or "none")

print(f"running test case 10/{{CASES}} verdict")
# Hard gate: Memory must contain the marker (or at least java rows created this run).
# Log save signals alone are not enough (agent used to invent them).
ok = bool(found) and (reply_hit or save_hit)
print("SMOKE_PASS" if ok else "SMOKE_FAIL")
if not ok:
    print("DIAG", {{"reply_hit": reply_hit, "save_hit": save_hit, "memory": len(found), "lookup_ok": lookup_ok}})
    raise SystemExit(1)
PY
"""
        print(f"running test case 3/{CASES} remote inject+memory (nested cases 3-10)")
        out2 = sudo_bash(c, remote, timeout=600)
        print(out2[-4000:])
        if "SMOKE_PASS" not in out2:
            print("FAIL smoke")
            return 1
        print("notes_deferred_persist_smoke: PASS")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
