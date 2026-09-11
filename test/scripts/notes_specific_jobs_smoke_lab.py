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
git checkout -B {BRANCH} origin/{BRANCH}
git reset --hard origin/{BRANCH}
bash run.sh load-openbao-env
python3 scripts/main/sync_router_worker_skills.py || true
SYNC_ZALO_RESTART=0 bash scripts/main/sync-zalo-plugins.sh
python3 test/scripts/notes_specific_jobs_unit.py
python3 test/scripts/notes_deferred_persist_unit.py
python3 test/scripts/notes_atomic_cite_unit.py
for id in $(docker ps --filter label=com.docker.compose.service=hermes --format '{{{{.ID}}}}'); do
  docker restart "$id" >/dev/null
done
sleep 25
echo DEPLOY_OK $(git rev-parse --short HEAD)
echo PROMPT_OK $(test -f hermes/main/skills/notes/prompts/search_then_note_listing.txt && echo yes || echo no)
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
# Probe classify JSON if endpoint available; soft evidence.
cls_ok=False
try:
    for url in ("http://127.0.0.1:8096/v1/classify", "http://router-worker:8096/v1/classify"):
        try:
            plan=post(url, {{"text": ask}}, timeout=60)
            flag=bool((plan or {{}}).get("persist_gathered_notes") is True) or (
                str((plan or {{}}).get("task_hint") or "").lower()=="search"
                and bool((plan or {{}}).get("process_original_message"))
            )
            print("CLASSIFY", url, "hint", (plan or {{}}).get("task_hint"), "persist", (plan or {{}}).get("persist_gathered_notes"))
            cls_ok=True
            break
        except Exception as e:
            print("CLASSIFY_TRY", type(e).__name__)
except Exception as e:
    print("CLASSIFY_ERR", type(e).__name__)
print("CLASSIFY_PROBED", cls_ok)

print(f"running test case 4/{{CASES}} inject search-then-note")
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

print(f"running test case 6/{{CASES}} Memory notes are concrete openings")
res=post("http://127.0.0.1:8095/v1/notes/query", {{"scope_id":f"zalo:user:{{user}}","query":marker,"limit":20}})
items=res.get("items") or []
if not items:
    res=post("http://127.0.0.1:8095/v1/notes/query", {{"scope_id":f"zalo:user:{{user}}","query":"java","limit":20}})
    items=res.get("items") or []
agg_notes=[i for i in items if agg_re.search(str((i or {{}}).get("content") or ""))]
spec_notes=[i for i in items if ("—" in str((i or {{}}).get("content") or "") or " - " in str((i or {{}}).get("content") or "")) and "http" in str((i or {{}}).get("content") or "").lower()]
print("NOTES", len(items), "AGG", len(agg_notes), "SPEC", len(spec_notes))
if items:
    print("NOTE_SAMPLE", str(items[0].get("content") or "")[:200])

print(f"running test case 7/{{CASES}} host save confirmation present")
saved=("note operation" in (reply or "").lower()) or ("đã lưu" in (reply or "").lower()) or ("da luu" in (reply or "").lower()) or ("ghi chú" in (reply or "").lower()) or ("ghi chu" in (reply or "").lower())
print("SAVED_CONFIRM", saved)

print(f"running test case 8/{{CASES}} re-inject same ask; prefer no new aggregate notes")
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
res2=post("http://127.0.0.1:8095/v1/notes/query", {{"scope_id":f"zalo:user:{{user}}","query":marker,"limit":50}})
items2=res2.get("items") or []
agg2=[i for i in items2 if agg_re.search(str((i or {{}}).get("content") or ""))]
print("NOTES2", len(items2), "AGG2", len(agg2))

print(f"running test case 9/{{CASES}} abnormal log scan")
scan=subprocess.check_output(
    "journalctl --user -u com.hermes.zaloplugin --since '40 min ago' --no-pager 2>/dev/null | grep -iE 'deferred note persist failed|UnboundLocalError|missing_notes' || true; "
    "docker logs --since 40m $(docker ps --filter label=com.docker.compose.service=hermes --format '{{{{.Names}}}}' | head -1) 2>&1 | grep -iE 'deferred note persist failed|UnboundLocalError' || true",
    shell=True, text=True, errors="replace",
)
print("ABNORMAL", (scan or "").strip()[:400] or "none")

print(f"running test case 10/{{CASES}} verdict elapsed={{round(time.time()-started,1)}}s")
# Hard gates: reply exists; no aggregate buckets stored; at least one specific cited note OR explicit no-new reply after first gather saved something.
ok = bool(reply) and len(agg_notes)==0 and len(agg2)==0 and (len(spec_notes)>0 or saved) and not reply_has_agg
print("SMOKE_PASS" if ok else "SMOKE_FAIL")
if not ok:
    print("DIAG", {{"reply":len(reply or ""),"agg":len(agg_notes),"spec":len(spec_notes),"saved":saved,"reply_agg":reply_has_agg,"agg2":len(agg2)}})
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
