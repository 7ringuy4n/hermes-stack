#!/usr/bin/env python3
"""Live DM/group concurrency lab using weather search and DOCX creation.

Runtime identities are resolved from environment and durable channel state.
Reports contain aggregate outcomes and timings, never numeric identities.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize  # noqa: E402

ROOT_OVERRIDE = (os.environ.get("ASSISTANT_REPO_ROOT") or "").strip()
ROOT = Path(ROOT_OVERRIDE) if ROOT_OVERRIDE else Path(__file__).resolve().parents[2]
OUT = ROOT / "test" / "reports" / "run-zalo-dm-group-capability-concurrency"
USER_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
GROUP_NAME = (os.environ.get("ZALO_TEST_GROUP_NAME") or "test").strip()


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def main() -> int:
    if not USER_ID or not GROUP_NAME:
        print("ERROR: runtime test user and group name are required", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    remote = rf'''
set -euo pipefail
cd /opt/assistant
python3 - <<'PY'
import concurrent.futures
import json
import os
import pathlib
import sqlite3
import subprocess
import time
import unicodedata
import urllib.request
import zipfile
from xml.etree import ElementTree

uid={USER_ID!r}
group_name={GROUP_NAME!r}.casefold()
tag=str(int(time.time()))

def post(path,payload,timeout=25):
    request=urllib.request.Request(
        "http://127.0.0.1:8787"+path,
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={{"Content-Type":"application/json"}},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(request,timeout=timeout).read().decode() or "{{}}")

def service_container(service):
    rows=subprocess.check_output(
        ["docker","ps","--filter","label=com.docker.compose.service="+service,"--format","{{{{.Names}}}}"],
        text=True,
    ).splitlines()
    if len(rows)!=1:
        raise SystemExit("FAIL_SERVICE_"+service.upper().replace("-","_"))
    return rows[0]

def parse_entries(path):
    rows=[]
    for raw in pathlib.Path(path).read_text(encoding="utf-8",errors="replace").splitlines():
        line=raw.strip()
        if not line or line.startswith("#"):
            continue
        ident,sep,name=line.partition("|")
        rows.append((ident.strip(),name.strip() if sep else ""))
    return rows

groups=[row for row in parse_entries("/data/assistant/zalo_allowed_threads.txt") if row[1].casefold()==group_name]
if len(groups)!=1:
    raise SystemExit("FAIL_GROUP_RESOLUTION")
gid=groups[0][0]

health=json.loads(urllib.request.urlopen("http://127.0.0.1:8787/health",timeout=8).read().decode() or "{{}}")
own=str(health.get("ownId") or "")
if not health.get("loggedIn") or int(health.get("sseClients") or 0)!=1 or not own:
    raise SystemExit("FAIL_BRIDGE_HEALTH")

zalo_api=service_container("zalo-api")
member_probe="""
import json, os, urllib.request
tid=os.environ["LAB_GROUP_ID"]
token=os.environ.get("ZALO_API_TOKEN","")
refresh=urllib.request.Request(
    "http://127.0.0.1:8100/v1/zalo/threads/"+tid+"/members/refresh",
    data=b"{{}}",
    headers={{"Authorization":"Bearer "+token,"Content-Type":"application/json"}},
    method="POST",
)
urllib.request.urlopen(refresh,timeout=15).read()
request=urllib.request.Request(
    "http://127.0.0.1:8100/v1/zalo/threads/"+tid+"/members",
    headers={{"Authorization":"Bearer "+token}},
)
print(json.dumps(json.loads(urllib.request.urlopen(request,timeout=10).read()),ensure_ascii=False))
"""
member_raw=subprocess.check_output(
    ["docker","exec","-e","LAB_GROUP_ID="+gid,zalo_api,"python3","-c",member_probe],
    text=True,
)
members=json.loads(member_raw).get("members") or []
member_ids={{str(row.get("zalo_user_id") or row.get("user_id") or row.get("id") or "") for row in members if isinstance(row,dict)}}
if len(members)!=3 or uid not in member_ids:
    raise SystemExit("FAIL_GROUP_MEMBERSHIP")

def inject(thread_id,thread_type,message_id,text):
    payload={{
        "threadId":thread_id,
        "threadType":thread_type,
        "senderId":uid,
        "senderName":"test-user",
        "messageId":message_id,
        "text":text,
        "isSelf":False,
    }}
    if thread_type=="group":
        payload["mentions"]=[own]
    return bool(post("/inject-event",{{"type":"message","payload":payload}}).get("ok"))

def delivery_rows(thread_id,thread_type,source_id,started):
    probe="""
import json, os, psycopg
with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    rows=conn.execute(
        "SELECT coalesce(content,''),coalesce(meta->>'delivery_kind','result'),"
        "coalesce(meta->>'attachment_kind',''),coalesce(meta->>'file_name',''),created_at "
        "FROM zalo_message_history WHERE thread_id=%s AND thread_type=%s "
        "AND event='delivered' AND created_at>=to_timestamp(%s) "
        "AND meta->>'source_message_id'=%s ORDER BY id",
        (os.environ["LAB_THREAD_ID"],os.environ["LAB_THREAD_TYPE"],
         int(os.environ["LAB_STARTED"]),os.environ["LAB_SOURCE_ID"]),
    ).fetchall()
print(json.dumps([[str(value) for value in row] for row in rows],ensure_ascii=False))
"""
    raw=subprocess.check_output(
        ["docker","exec","-e","LAB_THREAD_ID="+thread_id,"-e","LAB_THREAD_TYPE="+thread_type,
         "-e","LAB_STARTED="+str(int(started)),"-e","LAB_SOURCE_ID="+source_id,
         zalo_api,"python3","-c",probe],
        text=True,errors="replace",
    ).strip()
    return json.loads(raw or "[]")

def wait_deliveries(expected,started,kind,deadline_seconds):
    deadline=time.time()+deadline_seconds
    found={{}}
    latencies={{}}
    while time.time()<deadline:
        complete=True
        for label,row in expected.items():
            thread_id,thread_type,source_id=row
            rows=delivery_rows(thread_id,thread_type,source_id,started)
            if kind=="document":
                rows=[item for item in rows if len(item)>2 and item[2]=="document"]
            else:
                rows=[item for item in rows if len(item)>1 and item[1] in ("result","queue_recovery")]
            found[label]=rows
            if len(rows)!=1:
                complete=False
            elif label not in latencies:
                latencies[label]=round(time.time()-started,2)
        if complete:
            return found,latencies
        time.sleep(3)
    return found,latencies

def omni_search_rowid():
    attribution=service_container("omni-attribution")
    code="""
import sqlite3
conn=sqlite3.connect('/omni-data/storage.sqlite')
row=conn.execute("select coalesce(max(rowid),0) from call_logs where path='/v1/search'").fetchone()
print(int(row[0] or 0))
"""
    raw=subprocess.check_output(["docker","exec","-i",attribution,"python3","-c",code],text=True).strip()
    return int(raw or "0"),attribution

def omni_search_attribution(attribution,after_rowid):
    code="""
import os, sqlite3
conn=sqlite3.connect('/omni-data/storage.sqlite')
row=conn.execute(
    "select count(*) from call_logs where rowid>? and path='/v1/search' "
    "and requested_model='web-search' and combo_name='web-search'",
    (int(os.environ['LAB_AFTER_ROWID']),),
).fetchone()
print(int(row[0] or 0))
"""
    raw=subprocess.check_output(
        ["docker","exec","-e","LAB_AFTER_ROWID="+str(after_rowid),attribution,"python3","-c",code],
        text=True,
    ).strip()
    return int(raw or "0")

def folded(value):
    return "".join(
        char for char in unicodedata.normalize("NFKD",str(value).casefold())
        if not unicodedata.combining(char)
    )

search_rowid,attribution=omni_search_rowid()
weather_started=time.time()
weather_expected={{
    "dm":(uid,"user","weather-dm-"+tag),
    "group":(gid,"group","weather-group-"+tag),
}}
weather_prompts={{
    "dm":"Search the current weather in Da Nang. Reply with current temperature, conditions, and two source links.",
    "group":"Search the current weather in Hue. Reply with current temperature, conditions, and two source links.",
}}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    accepted={{label:pool.submit(inject,row[0],row[1],row[2],weather_prompts[label]) for label,row in weather_expected.items()}}
    weather_admission={{label:future.result() for label,future in accepted.items()}}
if not all(weather_admission.values()):
    raise SystemExit("FAIL_WEATHER_ADMISSION")
weather_rows,weather_latencies=wait_deliveries(weather_expected,weather_started,"text",300)
if any(len(rows)!=1 for rows in weather_rows.values()):
    raise SystemExit("FAIL_WEATHER_DELIVERY")
weather_text={{label:rows[0][0] for label,rows in weather_rows.items()}}
weather_objective={{
    "dm":"da nang" in folded(weather_text["dm"]),
    "group":"hue" in folded(weather_text["group"]),
}}
if not all(weather_objective.values()):
    raise SystemExit("FAIL_WEATHER_SEMANTICS")
attribution_deadline=time.time()+20
search_attributed=0
while time.time()<attribution_deadline:
    search_attributed=omni_search_attribution(attribution,search_rowid)
    if search_attributed>=2:
        break
    time.sleep(2)
if search_attributed<2:
    raise SystemExit("FAIL_WEATHER_ATTRIBUTION")

file_started=time.time()
file_expected={{
    "dm":(uid,"user","file-dm-"+tag),
    "group":(gid,"group","file-group-"+tag),
}}
file_markers={{"dm":"DOCX-DM-"+tag,"group":"DOCX-GROUP-"+tag}}
file_titles={{"dm":"Concurrent DM Report","group":"Concurrent Group Report"}}
file_prompts={{
    label:"Create and send one DOCX document. Use the title '"+file_titles[label]+"' and include this exact body marker: "+file_markers[label]
    for label in file_expected
}}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    accepted={{label:pool.submit(inject,row[0],row[1],row[2],file_prompts[label]) for label,row in file_expected.items()}}
    file_admission={{label:future.result() for label,future in accepted.items()}}
if not all(file_admission.values()):
    raise SystemExit("FAIL_FILE_ADMISSION")
file_rows,file_latencies=wait_deliveries(file_expected,file_started,"document",360)
if any(len(rows)!=1 for rows in file_rows.values()):
    raise SystemExit("FAIL_FILE_DELIVERY")

document_text={{}}
for label,rows in file_rows.items():
    file_name=rows[0][3]
    if not file_name or pathlib.Path(file_name).name!=file_name or not file_name.casefold().endswith(".docx"):
        raise SystemExit("FAIL_FILE_NAME")
    path=pathlib.Path("/data/assistant/media/out")/file_name
    if not path.is_file() or path.stat().st_size<1000:
        raise SystemExit("FAIL_FILE_MISSING")
    try:
        with zipfile.ZipFile(path) as archive:
            root=ElementTree.fromstring(archive.read("word/document.xml"))
    except (OSError,KeyError,zipfile.BadZipFile,ElementTree.ParseError):
        raise SystemExit("FAIL_FILE_PACKAGE")
    text=" ".join(value.strip() for value in root.itertext() if value.strip())
    document_text[label]=text
    if file_markers[label] not in text or file_titles[label] not in text:
        raise SystemExit("FAIL_FILE_CONTENT")

judge_payload={{"weather":weather_text,"documents":document_text}}
judge_prompt=(
    "Evaluate two concurrent weather answers and two generated document texts. "
    "The DM weather answer must clearly be current Da Nang weather with temperature and conditions. "
    "The group weather answer must clearly be current Hue weather with temperature and conditions. "
    "Each document must contain its distinct title and marker without content from the other conversation. "
    "Return JSON only with booleans dm_weather, group_weather, dm_document, group_document, scope_isolated "
    "and integer quality_score from 1 to 10. DATA="+json.dumps(judge_payload,ensure_ascii=False)
)
judge_code="""
import json, os, urllib.request
prompt=os.environ['LAB_JUDGE_PROMPT']
body=json.dumps({{'model':'classifier','stream':False,'max_tokens':300,'messages':[{{'role':'user','content':prompt}}]}}).encode()
base=(os.environ.get('OMNIROUTER_BASE_URL') or 'http://omni-router:20129/v1').rstrip('/')
key=(os.environ.get('OMNIROUTER_API_KEY') or '').strip()
request=urllib.request.Request(base+'/chat/completions',data=body,method='POST',headers={{'Authorization':'Bearer '+key,'Content-Type':'application/json'}})
with urllib.request.urlopen(request,timeout=180) as response:
    data=json.loads(response.read().decode() or '{{}}')
message=((data.get('choices') or [{{}}])[0].get('message') or {{}})
content=(message.get('content') or message.get('reasoning_content') or '').strip()
start=content.find('{{'); end=content.rfind('}}')
if start<0 or end<start: raise SystemExit(3)
print(content[start:end+1])
"""
dispatcher=service_container("dispatcher")
judge=subprocess.run(
    ["docker","exec","-e","LAB_JUDGE_PROMPT="+judge_prompt,dispatcher,"python3","-c",judge_code],
    text=True,capture_output=True,timeout=210,
)
judge_status="PASS"
evaluation={{}}
if judge.returncode!=0:
    diagnostic=((judge.stdout or "")+(judge.stderr or "")).casefold()
    if any(token in diagnostic for token in ("quota","rate limit","429","free model")):
        judge_status="SKIP_PROVIDER_QUOTA"
    else:
        raise SystemExit("FAIL_SEMANTIC_EVALUATOR")
else:
    try:
        evaluation=json.loads((judge.stdout or "").strip())
    except json.JSONDecodeError:
        raise SystemExit("FAIL_SEMANTIC_EVALUATOR_FORMAT")
    required=("dm_weather","group_weather","dm_document","group_document","scope_isolated")
    if not all(evaluation.get(key) is True for key in required) or int(evaluation.get("quality_score") or 0)<7:
        raise SystemExit("FAIL_SEMANTIC_QUALITY")

valkey=service_container("valkey")
drain_deadline=time.time()+45
active=[]
while time.time()<drain_deadline:
    active=subprocess.check_output(
        ["docker","exec",valkey,"valkey-cli","--raw","SMEMBERS","assistant:gate:qactive"],
        text=True,errors="replace",
    ).splitlines()
    if uid not in active and gid not in active:
        break
    time.sleep(1)
if uid in active or gid in active:
    raise SystemExit("FAIL_QUEUE_RESIDUE")

hermes_names=[name for name in subprocess.check_output(["docker","ps","--format","{{{{.Names}}}}"],text=True).splitlines() if name.startswith("assistant-hermes-")]
recent_logs=[]
for name in hermes_names:
    result=subprocess.run(["docker","logs","--since",str(int(weather_started)),name],text=True,capture_output=True)
    recent_logs.append((result.stdout or "")+(result.stderr or ""))
if "queue turn timeout" in "\n".join(recent_logs).casefold():
    raise SystemExit("FAIL_QUEUE_TIMEOUT")

print(json.dumps({{
    "ok":True,
    "bursts":2,
    "requests_per_burst":2,
    "destinations":["dm","group"],
    "group_members":len(members),
    "weather":{{
        "delivered":2,
        "objective":weather_objective,
        "web_search_attributed":search_attributed,
        "latency_s":weather_latencies,
        "elapsed_s":round(max(weather_latencies.values()),2),
    }},
    "files":{{
        "delivered":2,
        "packages_valid":True,
        "content_exact":True,
        "latency_s":file_latencies,
        "elapsed_s":round(max(file_latencies.values()),2),
    }},
    "semantic_evaluation":judge_status,
    "quality_score":int(evaluation.get("quality_score") or 0) if evaluation else None,
    "scope_isolated":True,
    "queue_empty":True,
    "queue_timeout":False,
}},separators=(",",":")))
PY
'''
    if (os.environ.get("ASSISTANT_TEST_LOCAL") or "").strip().casefold() in {"1", "true", "yes"}:
        completed = subprocess.run(
            ["bash", "-lc", remote],
            text=True,
            capture_output=True,
            timeout=900,
        )
        raw = sanitize((completed.stdout or "") + (completed.stderr or ""))
    else:
        from deploy_stack import connect, sudo_bash

        client = connect()
        try:
            raw = sanitize(sudo_bash(client, remote, timeout=900) or "")
        finally:
            client.close()
    line = next((row for row in reversed(raw.splitlines()) if row.startswith("{")), "")
    try:
        result = json.loads(line)
    except json.JSONDecodeError:
        failure = next((row for row in reversed(raw.splitlines()) if row.startswith("FAIL_")), "missing_result")
        result = {"ok": False, "error": failure}
    report = {"timestamp": timestamp(), "result": result}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
