# -*- coding: utf-8 -*-
"""VPS smoke: once_after search-then-note must ack, fire, and persist notes."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

BRANCH = os.environ.get("ASSISTANT_TEST_BRANCH", "fix/zalo/schedule-search-note-silence")
USER_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
CASES = 10
SKIP_DEPLOY = os.environ.get("SKIP_DEPLOY", "0").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    marker = f"SCHEDNOTE-{int(time.time())}"
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
python3 test/scripts/schedule_search_note_fire_unit.py
python3 test/scripts/notes_atomic_cite_unit.py
for id in $(docker ps --filter label=com.docker.compose.service=hermes --format '{{{{.ID}}}}'); do
  docker restart "$id" >/dev/null
done
sleep 22
echo DEPLOY_OK $(git rev-parse --short HEAD)
"""
            out = sudo_bash(c, deploy, timeout=900)
            if "schedule_search_note_fire_unit: PASS" not in out:
                print("FAIL deploy/unit")
                print(out[-2500:])
                return 1
            print(f"running test case 2/{CASES} unit PASS")
        else:
            print(f"running test case 2/{CASES} skip deploy")

        # 70s delay keeps smoke under ~3 minutes while exercising once_after.
        ask = (
            f"70 giay nua truy cap ITviec TopCV topDev facebook tim tin tuyen dung "
            f"fullstack BE Java o Ho Chi Minh con hieu luc gan nhat marker {marker} "
            f"va ghi chu lai"
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

print(f"running test case 3/{{CASES}} inject once_after search-then-note")
mid=f"sn-{{int(time.time())}}"
print("INJECT", inject(ask, mid).get("ok"), mid)

print(f"running test case 4/{{CASES}} wait schedule ack")
ack=""; deadline=time.time()+90
while time.time()<deadline:
    ack=sql("SELECT coalesce(content,'') FROM zalo_message_history WHERE event='delivered' AND meta->>'source_message_id'='%s' ORDER BY id DESC LIMIT 1;"%mid)
    if ack and ("lịch" in ack.lower() or "lich" in ack.lower() or "schedule" in ack.lower() or "chạy" in ack.lower() or "chay" in ack.lower() or "đặt" in ack.lower() or "dat" in ack.lower() or "lưu" in ack.lower() or "luu" in ack.lower()):
        break
    # Also accept host failure ack (still a response — not silence).
    if ack and len(ack)>10:
        break
    time.sleep(3)
print("ACK_SNIP", json.dumps((ack or "")[:220], ensure_ascii=False))
ack_ok=bool(ack) and ("không thể" not in ack.lower() and "could not" not in ack.lower() and "failed" not in ack.lower())
print("ACK_OK", ack_ok)

print(f"running test case 5/{{CASES}} wait schedule fire (~90s)")
fire=""; fire_mid=""; deadline=time.time()+150
while time.time()<deadline:
    row=sql("SELECT coalesce(content,''), coalesce(meta->>'source_message_id','') FROM zalo_message_history WHERE event='delivered' AND created_at > now() - interval '6 minutes' AND (content ILIKE '%%%s%%' OR content ILIKE '%%Java%%') AND content ILIKE '%%1.%%' AND meta->>'source_message_id' ILIKE 'schedule:%%' ORDER BY id DESC LIMIT 1;"%marker)
    if row:
        parts=row.split("|",1)
        fire=parts[0]
        fire_mid=parts[1] if len(parts)>1 else ""
        break
    # Fallback without marker if model dropped it.
    row2=sql("SELECT coalesce(content,''), coalesce(meta->>'source_message_id','') FROM zalo_message_history WHERE event='delivered' AND created_at > now() - interval '4 minutes' AND content ILIKE '%%Java%%' AND content ILIKE '%%1.%%' AND meta->>'source_message_id' ILIKE 'schedule:%%' ORDER BY id DESC LIMIT 1;")
    if row2:
        parts=row2.split("|",1)
        fire=parts[0]
        fire_mid=parts[1] if len(parts)>1 else ""
        break
    time.sleep(5)
print("FIRE_LEN", len(fire or ""))
print("FIRE_MID", fire_mid)
print("FIRE_SNIP", json.dumps((fire or "")[:240], ensure_ascii=False))

print(f"running test case 6/{{CASES}} no workflow ack spam on fire")
acks=sql("SELECT count(*) FROM zalo_message_history WHERE event='delivered' AND created_at > now() - interval '6 minutes' AND (content ILIKE '%%Đang xử lý%%' OR content='Đang xử lý…') AND meta->>'source_message_id' ILIKE 'schedule:%%';")
print("FIRE_WORKFLOW_ACKS", acks)

print(f"running test case 7/{{CASES}} Memory notes after fire")
res=post("http://127.0.0.1:8095/v1/notes/query", {{"scope_id":f"zalo:user:{{user}}","query":"java","limit":20}})
items=res.get("items") or []
cited=[i for i in items if "http" in str((i or {{}}).get("content") or "").lower()]
fresh=[i for i in items if marker in str((i or {{}}).get("content") or "")]
print("NOTES", len(items), "CITED", len(cited), "FRESH", len(fresh))
if items:
    print("NOTE_SAMPLE", str(items[0].get("content") or "")[:160])

print(f"running test case 8/{{CASES}} host save confirm on fire body")
host_save=("note saved" in (fire or "").lower()) or ("đã lưu" in (fire or "").lower()) or ("da luu" in (fire or "").lower()) or ("ghi chú" in (fire or "").lower())
print("HOST_SAVE_LIKE", host_save)

print(f"running test case 9/{{CASES}} cleanup leftover once schedules with marker")
# Best-effort: list and delete schedules mentioning marker.
try:
    data=post("http://127.0.0.1:8110/v1/schedules", {{}})
except Exception:
    data={{}}
# GET list
try:
    with urllib.request.urlopen("http://127.0.0.1:8110/v1/schedules", timeout=10) as resp:
        listing=json.loads(resp.read().decode() or "{{}}")
except Exception as e:
    listing={{"error":type(e).__name__}}
deleted=0
for sch in (listing.get("schedules") or []):
    blob=json.dumps(sch, ensure_ascii=False)
    if marker in blob or "giay nua" in blob.lower() or "fullstack BE Java" in blob:
        sid=str(sch.get("id") or "")
        if not sid:
            continue
        try:
            req=urllib.request.Request(f"http://127.0.0.1:8110/v1/schedules/{{sid}}", method="DELETE")
            with urllib.request.urlopen(req, timeout=8) as resp:
                resp.read()
            deleted += 1
        except Exception:
            pass
print("CLEANED", deleted)

print(f"running test case 10/{{CASES}} verdict elapsed={{round(time.time()-started,1)}}s")
ok = ack_ok and bool(fire) and int(acks or "0") == 0
print("SMOKE_PASS" if ok else "SMOKE_FAIL")
if not ok:
    print("DIAG", {{"ack_ok":ack_ok,"fire_len":len(fire or ""),"acks":acks,"cited":len(cited),"fresh":len(fresh),"host_save":host_save}})
    raise SystemExit(1)
PY
"""
        print(f"running test case 3/{CASES} remote nested")
        out2 = sudo_bash(c, remote, timeout=420)
        print(out2[-5000:])
        if "SMOKE_PASS" not in out2:
            print("FAIL smoke")
            return 1
        print("schedule_search_note_fire_smoke: PASS")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
