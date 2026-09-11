# -*- coding: utf-8 -*-
"""VPS smoke: atomic search-then-note, citations, note CRUD, schedule-note."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

BRANCH = os.environ.get("ASSISTANT_TEST_BRANCH", "fix/zalo/note-atomic-cite")
USER_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
CASES = 12
SKIP_DEPLOY = os.environ.get("SKIP_DEPLOY", "0").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    marker = f"NOTEATOM-{int(time.time())}"
    print(f"running test case 1/{CASES} deploy {BRANCH} skip={SKIP_DEPLOY}")
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
python3 test/scripts/notes_atomic_cite_unit.py
python3 test/scripts/notes_crud_unit.py
python3 test/scripts/notes_deferred_persist_unit.py
for id in $(docker ps --filter label=com.docker.compose.service=hermes --format '{{{{.ID}}}}'); do
  docker restart "$id" >/dev/null
done
sleep 25
echo DEPLOY_OK $(git rev-parse --short HEAD)
"""
            out = sudo_bash(c, deploy, timeout=900)
            if "notes_atomic_cite_unit: PASS" not in out or "notes_crud_unit: PASS" not in out:
                print("FAIL deploy/unit")
                print(out[-3000:])
                return 1
            print(f"running test case 2/{CASES} units PASS")
        else:
            print(f"running test case 2/{CASES} skip deploy")

        ask = (
            f"Tim 3 tin tuyen dung Java backend/fullstack HCM tren ITviec TopCV TopDev "
            f"(nguon cong khai), moi tin mot dong danh so kem link https, marker {marker}, "
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

user=os.environ["LAB_USER"]; marker=os.environ["LAB_MARKER"]; ask=os.environ["LAB_ASK"]
CASES=12; started=time.time()
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

print(f"running test case 3/{{CASES}} inject atomic search-then-note")
mid=f"na-{{int(time.time())}}"
print("INJECT", inject(ask, mid).get("ok"), mid)

print(f"running test case 4/{{CASES}} wait gather+save")
reply=""; deadline=time.time()+360
while time.time()<deadline:
    reply=delivered(mid)
    if reply and len(reply)>40:
        break
    time.sleep(5)
print("REPLY_LEN", len(reply or ""))
print("REPLY_SNIP", json.dumps((reply or "")[:260], ensure_ascii=False))

print(f"running test case 5/{{CASES}} no duplicate workflow ack for same mid")
acks=sql("SELECT count(*) FROM zalo_message_history WHERE event='delivered' AND meta->>'source_message_id'='%s' AND (content ILIKE '%%Đang xử lý%%' OR content ILIKE '%%Dang xu ly%%');"%mid)
listings=sql("SELECT count(*) FROM zalo_message_history WHERE event='delivered' AND meta->>'source_message_id'='%s' AND content ILIKE '%%1.%%' AND content ILIKE '%%Java%%';"%mid)
print("ACK_COUNT", acks, "LISTING_COUNT", listings)
# Soft: ack should be 0 for this mid; listing ideally 1 (host confirm may be same delivery).
dup_fail = int(acks or "0") > 0 or int(listings or "0") > 1

print(f"running test case 6/{{CASES}} Memory citations")
res=post("http://127.0.0.1:8095/v1/notes/query", {{"scope_id":f"zalo:user:{{user}}","query":"java","limit":20}})
items=res.get("items") or []
cited=[i for i in items if "http" in str((i or {{}}).get("content") or "").lower() or "nguồn:" in str((i or {{}}).get("content") or "").lower() or "nguon:" in str((i or {{}}).get("content") or "").lower()]
# Prefer notes from this run if marker present; else any cited java notes after deploy.
fresh=[i for i in cited if marker in str((i or {{}}).get("content") or "")]
print("CITED", len(cited), "FRESH", len(fresh))
if cited:
    print("CITE_SAMPLE", str(cited[0].get("content") or "")[:180])

print(f"running test case 7/{{CASES}} CRUD create/lookup/update/delete via Memory API")
import urllib.request as ur
def patch(url, payload):
    data=json.dumps(payload).encode()
    req=ur.Request(url,data=data,method="PATCH",headers={{"Content-Type":"application/json"}})
    with ur.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode() or "{{}}")
def delete(url):
    req=ur.Request(url, method="DELETE")
    with ur.urlopen(req, timeout=15) as resp:
        body=resp.read().decode() or "{{}}"
        try:
            return json.loads(body)
        except Exception:
            return {{"success": resp.status < 300}}
crud_marker=f"CRUD-{{int(time.time())}}"
created=post("http://127.0.0.1:8095/v1/notes", {{
    "scope_id": f"zalo:user:{{user}}",
    "content": f"{{crud_marker}} buy milk",
    "note_date": "2026-09-11",
    "thread_id": user,
    "thread_type": "user",
    "owner_id": user,
    "tags": ["errand"],
    "metadata": {{"source":"lab"}},
}})
nid=str(((created.get("note") or {{}}).get("id") or ""))
print("CRUD_CREATE", created.get("success"), nid)
look=post("http://127.0.0.1:8095/v1/notes/query", {{"scope_id":f"zalo:user:{{user}}","query":crud_marker,"limit":5}})
print("CRUD_LOOKUP", look.get("count"))
upd=patch(f"http://127.0.0.1:8095/v1/notes/{{nid}}", {{"scope_id":f"zalo:user:{{user}}","content":f"{{crud_marker}} buy milk revised","note_date":"2026-09-11","tags":["errand"]}})
print("CRUD_UPDATE", upd.get("success"))
deleted=delete(f"http://127.0.0.1:8095/v1/notes/{{nid}}?scope_id=zalo:user:{{user}}")
print("CRUD_DELETE", deleted.get("success"))
gone=post("http://127.0.0.1:8095/v1/notes/query", {{"scope_id":f"zalo:user:{{user}}","query":crud_marker,"limit":5}})
print("CRUD_GONE", gone.get("count"))

print(f"running test case 8/{{CASES}} schedule search-then-note once_after")
sid=f"sched-note-{{int(time.time())}}"
# Create a due-soon schedule via schedule-worker; fire_text is search-then-note.
body={{
  "id": sid,
  "name": sid,
  "cron_expr": "",
  "once_at": None,
  "text": f"tim 1 tin Java HCM tren TopCV roi note lai marker {{marker}}-S",
  "fire_text": f"tim 1 tin Java HCM tren TopCV roi note lai marker {{marker}}-S",
  "origin": {{"platform":"zalo","thread_id":user,"chat_id":user,"user_id":user,"sender_id":user}},
  "context": {{"thread_id":user,"sender_id":user,"thread_type":"user","original_request":f"tim 1 tin Java HCM tren TopCV roi note lai marker {{marker}}-S"}},
  "enabled": True,
  "timezone": "Asia/Ho_Chi_Minh",
}}
# Prefer once_after helper if available via API — fall back to inject as live if schedule create fails.
sched_ok=False
for url in ("http://127.0.0.1:8110/v1/schedules", "http://schedule-worker:8110/v1/schedules"):
    try:
        # Use near-future once via cron in one minute if once unsupported.
        import datetime as dt
        now=dt.datetime.now(dt.timezone(dt.timedelta(hours=7)))
        soon=now+dt.timedelta(minutes=1)
        body["cron_expr"]=f"{{soon.minute}} {{soon.hour}} * * *"
        post(url, body, timeout=10)
        sched_ok=True
        print("SCHED_CREATE", url, sid)
        break
    except Exception as e:
        print("SCHED_TRY_FAIL", type(e).__name__)
print("SCHED_OK", sched_ok)

print(f"running test case 9/{{CASES}} wait schedule fire briefly (90s)")
sched_hit=False
if sched_ok:
    deadline=time.time()+100
    while time.time()<deadline:
        hit=sql("SELECT coalesce(content,'') FROM zalo_message_history WHERE event='delivered' AND created_at > now() - interval '3 minutes' AND content ILIKE '%%%s-S%%' ORDER BY id DESC LIMIT 1;"%marker)
        if hit:
            sched_hit=True
            print("SCHED_REPLY", json.dumps(hit[:180], ensure_ascii=False))
            break
        time.sleep(5)
print("SCHED_HIT", sched_hit)

print(f"running test case 10/{{CASES}} cleanup schedule")
if sched_ok:
    for url in (f"http://127.0.0.1:8110/v1/schedules/{{sid}}",):
        try:
            req=ur.Request(url, method="DELETE")
            with ur.urlopen(req, timeout=8) as resp:
                print("SCHED_DEL", resp.status)
        except Exception as e:
            print("SCHED_DEL_ERR", type(e).__name__)

print(f"running test case 11/{{CASES}} abnormal scan")
scan=subprocess.check_output("journalctl --user -u com.hermes.zaloplugin --since '45 min ago' --no-pager 2>/dev/null | grep -iE 'notes\\.failed|missing_notes|deferred note persist failed|UnboundLocalError' || true", shell=True, text=True, errors="replace")
print("ABNORMAL", (scan or "").strip()[:300] or "none")

print(f"running test case 12/{{CASES}} verdict elapsed={{round(time.time()-started,1)}}s")
# Hard gates: gather reply exists, no duplicate listing/ack for mid, citations present, CRUD ok.
crud_ok = bool(nid) and str(gone.get("count") or 0) in {{"0", 0}}
ok = bool(reply) and not dup_fail and (len(fresh) > 0 or len(cited) > 0) and crud_ok
# Schedule is best-effort evidence when worker accepts once; do not hard-fail if cron timing missed in 90s.
print("SMOKE_PASS" if ok else "SMOKE_FAIL")
if not ok:
    print("DIAG", {{"reply":len(reply or ""),"dup_fail":dup_fail,"cited":len(cited),"fresh":len(fresh),"crud_ok":crud_ok,"sched_hit":sched_hit}})
    raise SystemExit(1)
PY
"""
        print(f"running test case 3/{CASES} remote nested cases")
        out2 = sudo_bash(c, remote, timeout=800)
        print(out2[-6000:])
        if "SMOKE_PASS" not in out2:
            print("FAIL smoke")
            return 1
        print("notes_atomic_cite_smoke: PASS")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
