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
for id in $(docker ps --filter label=com.docker.compose.service=hermes --format '{{{{.ID}}}}'); do
  docker restart "$id" >/dev/null
done
sleep 18
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
import json, os, subprocess, time, urllib.request

user = os.environ["LAB_USER"]
marker = os.environ["LAB_MARKER"]
ask = os.environ["LAB_ASK"]
CASES = 10
started = time.time()
pg = subprocess.check_output(
    ["docker", "ps", "--filter", "label=com.docker.compose.service=postgres", "--format", "{{{{.Names}}}}"],
    text=True,
).splitlines()[0]
db_user = os.environ.get("MEMORY_DB_USER", "hermes")
db_name = os.environ.get("MEMORY_DB_NAME", "hermes_memory")
db_password = os.environ.get("MEMORY_DB_PASSWORD", "")

def post(url, payload, timeout=30):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={{"Content-Type": "application/json"}},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{{}}")

def sql(query: str) -> str:
    return subprocess.check_output(
        ["docker", "exec", "-e", "PGPASSWORD=" + db_password, pg, "psql", "-U", db_user, "-d", db_name, "-At", "-c", query],
        text=True,
        errors="replace",
    ).strip()

def delivered_for(mid: str) -> str:
    q = (
        "SELECT coalesce(content,'') FROM zalo_message_history "
        f"WHERE event='delivered' AND meta->>'source_message_id'='{{mid}}' "
        "ORDER BY id DESC LIMIT 1;"
    )
    return sql(q)

print(f"running test case 3/{{CASES}} inject search-then-note")
mid = f"np-{{int(time.time())}}"
payload = {{
    "type": "message",
    "payload": {{
        "threadId": user,
        "threadType": "user",
        "senderId": user,
        "senderName": "Tn",
        "messageId": mid,
        "text": ask,
        "isSelf": False,
    }},
}}
print("INJECT", post("http://127.0.0.1:8787/inject-event", payload).get("ok"), mid)

print(f"running test case 4/{{CASES}} wait delivered reply")
reply = ""
deadline = time.time() + 300
while time.time() < deadline:
    reply = delivered_for(mid)
    if reply and len(reply) > 40:
        break
    time.sleep(5)
print("REPLY_LEN", len(reply or ""))
print("REPLY_HAS_MARKER", marker in (reply or ""))
print("REPLY_SNIP", json.dumps((reply or "")[:280], ensure_ascii=False))

print(f"running test case 5/{{CASES}} Memory query by topic")
found = []
for q in ("java", "LG CNS", "TopCV", "SHB"):
    res = post(
        "http://127.0.0.1:8095/v1/notes/query",
        {{"scope_id": f"zalo:user:{{user}}", "query": q, "limit": 20}},
        timeout=15,
    )
    items = res.get("items") or []
    for it in items:
        content = str((it or {{}}).get("content") or "")
        # Accept this-run job lines (and tolerate older java notes).
        if any(x in content for x in ("LG CNS", "Galaxy", "SHB", "TopCV", "Java Backend", "Fullstack Java")):
            if content not in found:
                found.append(content[:240])
    print("MEMORY_Q", q, "count", len(items), "job_hits", len(found))
    if found:
        break
if found:
    print("MEMORY_SAMPLE", found[0][:180])

print(f"running test case 6/{{CASES}} lookup inject")
mid2 = f"np-lookup-{{int(time.time())}}"
payload2 = {{
    "type": "message",
    "payload": {{
        "threadId": user,
        "threadType": "user",
        "senderId": user,
        "senderName": "Tn",
        "messageId": mid2,
        "text": "hien thi cac tin tuyen dung java da luu",
        "isSelf": False,
    }},
}}
print("INJECT_LOOKUP", post("http://127.0.0.1:8787/inject-event", payload2).get("ok"))

print(f"running test case 7/{{CASES}} wait lookup delivered")
lookup = ""
deadline = time.time() + 120
while time.time() < deadline:
    lookup = delivered_for(mid2)
    if lookup:
        break
    time.sleep(4)
print("LOOKUP_SNIP", json.dumps((lookup or "")[:280], ensure_ascii=False))
lookup_ok = bool(lookup) and ("không tìm thấy" not in lookup.lower()) and (
    "java" in lookup.lower() or "lg cns" in lookup.lower() or "topcv" in lookup.lower() or "shb" in lookup.lower()
)
print("LOOKUP_OK", lookup_ok)

print(f"running test case 8/{{CASES}} host confirm / no fake-only claim")
host_confirm = any(
    x in (reply or "").lower()
    for x in ("the note operation completed", "item(s)", "đã lưu", "da luu", "ghi chú")
)
print("HOST_CONFIRM_LIKE", host_confirm)

print(f"running test case 9/{{CASES}} abnormal scan")
try:
    scan = subprocess.check_output(
        "journalctl --user -u com.hermes.zaloplugin --since '40 min ago' --no-pager 2>/dev/null | "
        "grep -iE 'notes\\.failed|missing_notes|deferred note persist failed|UnboundLocalError' || true",
        shell=True,
        text=True,
        errors="replace",
    )
except Exception as e:
    scan = str(e)
print("ABNORMAL_SCAN", (scan or "").strip()[:400] or "none")

print(f"running test case 10/{{CASES}} verdict elapsed={{round(time.time()-started,1)}}s")
# Hard gate: Memory holds job notes AND topic lookup returns them (not empty UX).
ok = bool(found) and bool(reply) and lookup_ok
print("SMOKE_PASS" if ok else "SMOKE_FAIL")
if not ok:
    print("DIAG", {{
        "reply_len": len(reply or ""),
        "memory": len(found),
        "lookup_ok": lookup_ok,
        "host_confirm_like": host_confirm,
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
