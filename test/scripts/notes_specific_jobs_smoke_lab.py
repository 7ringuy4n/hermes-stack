# -*- coding: utf-8 -*-
"""VPS smoke: skill-owned specific job notes (no aggregate buckets)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

BRANCH = os.environ.get("ASSISTANT_TEST_BRANCH", "fix/zalo/note-specific-jobs")
USER_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
CASES = 10
SKIP_DEPLOY = os.environ.get("SKIP_DEPLOY", "0").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    marker = f"NOTESPEC-{int(time.time())}"
    print(f"running test case 1/{CASES} deploy {BRANCH} skip={SKIP_DEPLOY}")
    c = connect()
    try:
        if not SKIP_DEPLOY:
            deploy = f"""
set -euo pipefail
cd /opt/assistant
sudo chown -R tn:tn /opt/assistant /data/assistant 2>/dev/null || true
git fetch origin {BRANCH} main develop
git reset --hard HEAD
git clean -fd -- hermes architect test history docs || true
git checkout -f -B {BRANCH} origin/{BRANCH}
git reset --hard origin/{BRANCH}
bash run.sh load-openbao-env
python3 scripts/main/sync_router_worker_skills.py || true
SYNC_ZALO_RESTART=0 bash scripts/main/sync-zalo-plugins.sh
# classify.py is image-baked; rebuild via run.sh so env interpolation works.
bash run.sh sync-openbao-env || true
python3 test/scripts/notes_specific_jobs_unit.py
python3 test/scripts/notes_deferred_persist_unit.py
python3 test/scripts/notes_atomic_cite_unit.py
sleep 20
echo DEPLOY_OK $(git rev-parse --short HEAD)
echo PROMPT_OK $(test -f hermes/main/skills/notes/prompts/search_then_note_listing.txt && echo yes || echo no)
echo CLASSIFY_HAS_PERSIST $(docker exec router-worker grep -c persist_gathered_notes /app/classify.py || true)
"""
            out = sudo_bash(c, deploy, timeout=900)
            if "notes_specific_jobs_unit: PASS" not in out:
                print("FAIL deploy/unit")
                print(out[-4000:])
                return 1
            if "PROMPT_OK yes" not in out:
                print("FAIL prompt asset missing")
                print(out[-2000:])
                return 1
            print(f"running test case 2/{CASES} units PASS deploy={out.split('DEPLOY_OK')[-1].strip()[:40]}")
        else:
            print(f"running test case 2/{CASES} skip deploy")

        ask = (
            f"Tim tin tuyen dung fullstack BE Java o HCM tren ITviec TopCV TopDev "
            f"(nguon cong khai). Chi liet ke cac tin cu the dang Title (stack) — Employer "
            f"kem link https, khong liet ke bucket tong hop kieu ~N tin. Marker {marker}. "
            f"Sau do note lai."
        )
        remote = f"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
export LAB_USER='{USER_ID}'
export LAB_MARKER='{marker}'
export LAB_ASK={json.dumps(ask)}
python3 - <<'PY'
import json, os, subprocess, time, urllib.request, re

user=os.environ["LAB_USER"]; marker=os.environ["LAB_MARKER"]; ask=os.environ["LAB_ASK"]
CASES=10; started=time.time()
pg=subprocess.check_output(["docker","ps","--filter","label=com.docker.compose.service=postgres","--format","{{{{.Names}}}}"],text=True).splitlines()[0]
db_user=os.environ.get("MEMORY_DB_USER","hermes"); db_name=os.environ.get("MEMORY_DB_NAME","hermes_memory"); db_password=os.environ.get("MEMORY_DB_PASSWORD","")

def post(url, payload, timeout=30):
    data=json.dumps(payload, ensure_ascii=False).encode()
    req=urllib.request.Request(url,data=data,method="POST",headers={{"Content-Type":"application/json"}})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{{}}")

def sql(q):
    return subprocess.check_output(["docker","exec","-e","PGPASSWORD="+db_password,pg,"psql","-U",db_user,"-d",db_name,"-At","-c",q],text=True,errors="replace").strip()

def inject(text, mid):
    payload={{"type":"message","payload":{{"threadId":user,"threadType":"user","senderId":user,"senderName":"Tn","messageId":mid,"text":text,"isSelf":False}}}}
    return post("http://127.0.0.1:8787/inject-event", payload)

def delivered(mid):
    return sql("SELECT coalesce(content,'') FROM zalo_message_history WHERE event='delivered' AND meta->>'source_message_id'='%s' ORDER BY id DESC LIMIT 1;"%mid)

agg_re=re.compile(r"(?i)(~\\s*\\d+\\s*tin|khoảng\\s+\\d+\\s*tin|about\\s+\\d+\\s*jobs?)")

print(f"running test case 3/{{CASES}} classify persist_gathered_notes probe")
cls_persist=False
try:
    for url in ("http://127.0.0.1:8096/v1/classify", "http://router-worker:8096/v1/classify"):
        try:
            plan=post(url, {{"text": ask}}, timeout=90)
            print("CLASSIFY", url, "hint", (plan or {{}}).get("task_hint"), "persist", (plan or {{}}).get("persist_gathered_notes"))
            cls_persist=bool((plan or {{}}).get("persist_gathered_notes") is True)
            break
        except Exception as e:
            print("CLASSIFY_TRY", type(e).__name__)
except Exception as e:
    print("CLASSIFY_ERR", type(e).__name__)
print("CLASSIFY_PERSIST", cls_persist)

print(f"running test case 4/{{CASES}} inject search-then-note")
t0=time.time()
mid=f"ns-{{int(time.time())}}"
print("INJECT", inject(ask, mid).get("ok"), mid)

print(f"running test case 5/{{CASES}} wait gather+host save")
reply=""; deadline=time.time()+360
while time.time()<deadline:
    reply=delivered(mid)
    if reply and len(reply)>40:
        break
    time.sleep(5)
print("REPLY_LEN", len(reply or ""))
print("REPLY_SNIP", json.dumps((reply or "")[:320], ensure_ascii=False))
reply_has_agg=bool(agg_re.search(reply or ""))
print("REPLY_HAS_AGG", reply_has_agg)

print(f"running test case 6/{{CASES}} Memory notes created after inject")
# Only notes created after this inject; ignore historical aggregates.
fresh_sql=sql(
    "SELECT coalesce(content,'') FROM notes WHERE scope_id='zalo:user:%s' AND active AND created_at > to_timestamp(%s) ORDER BY created_at DESC LIMIT 30;"
    % (user, int(t0)-5)
)
fresh_lines=[ln for ln in (fresh_sql or "").split("\\n") if ln.strip()] if False else []
# psql -At may return rows separated by newlines; content itself may contain newlines replaced earlier — use API with time filter via SQL count.
fresh_rows=subprocess.check_output(
    ["docker","exec","-e","PGPASSWORD="+db_password,pg,"psql","-U",db_user,"-d",db_name,"-At","-c",
     "SELECT id||E'\\t'||left(regexp_replace(content, E'[\\\\n\\\\r]+', ' ', 'g'),200) FROM notes WHERE scope_id='zalo:user:%s' AND active AND created_at > now() - interval '15 minutes' ORDER BY created_at DESC LIMIT 30;"%user],
    text=True, errors="replace",
).strip().splitlines()
agg_notes=[r for r in fresh_rows if agg_re.search(r)]
spec_notes=[r for r in fresh_rows if ("—" in r or " - " in r) and "http" in r.lower()]
print("FRESH", len(fresh_rows), "AGG", len(agg_notes), "SPEC", len(spec_notes))
if fresh_rows:
    print("NOTE_SAMPLE", fresh_rows[0][:200])

print(f"running test case 7/{{CASES}} host save confirmation present")
saved=("note operation completed" in (reply or "").lower()) or ("the note operation" in (reply or "").lower()) or ("đã lưu" in (reply or "").lower()) or ("da luu" in (reply or "").lower())
print("SAVED_CONFIRM", saved)

print(f"running test case 8/{{CASES}} re-inject; no new aggregate rows")
mid2=f"ns2-{{int(time.time())}}"
print("INJECT2", inject(ask+" (lan 2)", mid2).get("ok"), mid2)
reply2=""; deadline=time.time()+300
while time.time()<deadline:
    reply2=delivered(mid2)
    if reply2 and len(reply2)>20:
        break
    time.sleep(5)
print("REPLY2_LEN", len(reply2 or ""))
print("REPLY2_SNIP", json.dumps((reply2 or "")[:240], ensure_ascii=False))
fresh_rows2=subprocess.check_output(
    ["docker","exec","-e","PGPASSWORD="+db_password,pg,"psql","-U",db_user,"-d",db_name,"-At","-c",
     "SELECT left(regexp_replace(content, E'[\\\\n\\\\r]+', ' ', 'g'),200) FROM notes WHERE scope_id='zalo:user:%s' AND active AND created_at > now() - interval '20 minutes' ORDER BY created_at DESC LIMIT 40;"%user],
    text=True, errors="replace",
).strip().splitlines()
agg2=[r for r in fresh_rows2 if agg_re.search(r)]
print("FRESH2", len(fresh_rows2), "AGG2", len(agg2))

print(f"running test case 9/{{CASES}} abnormal log scan")
scan=subprocess.check_output(
    "journalctl --user -u com.hermes.zaloplugin --since '40 min ago' --no-pager 2>/dev/null | grep -iE 'deferred note persist failed|UnboundLocalError|missing_notes' || true; "
    "docker logs --since 40m $(docker ps --filter label=com.docker.compose.service=hermes --format '{{{{.Names}}}}' | head -1) 2>&1 | grep -iE 'deferred note persist failed|UnboundLocalError' || true",
    shell=True, text=True, errors="replace",
)
print("ABNORMAL", (scan or "").strip()[:400] or "none")

print(f"running test case 10/{{CASES}} verdict elapsed={{round(time.time()-started,1)}}s")
ok = (
    bool(reply)
    and cls_persist
    and len(agg_notes)==0
    and len(agg2)==0
    and len(spec_notes)>0
    and saved
    and not reply_has_agg
)
print("SMOKE_PASS" if ok else "SMOKE_FAIL")
if not ok:
    print("DIAG", {{"reply":len(reply or ""),"cls_persist":cls_persist,"agg":len(agg_notes),"spec":len(spec_notes),"saved":saved,"reply_agg":reply_has_agg,"agg2":len(agg2)}})
    raise SystemExit(1)
PY
"""
        print(f"running test case 3/{CASES} remote nested cases")
        out2 = sudo_bash(c, remote, timeout=900)
        print(out2[-8000:])
        if "SMOKE_PASS" not in out2:
            print("FAIL smoke")
            return 1
        print("notes_specific_jobs_smoke: PASS")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
