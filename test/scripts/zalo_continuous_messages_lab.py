#!/usr/bin/env python3
"""Live Zalo lab for per-destination FIFO context and quote correlation.

Runtime identities come from environment and durable channel state. Reports
contain aggregate outcomes only.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402
from sanitize import sanitize  # noqa: E402

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-continuous-messages"
USER_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
GROUP_NAME = (os.environ.get("ZALO_TEST_GROUP_NAME") or "test").strip()


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def main() -> int:
    if not USER_ID or not GROUP_NAME:
        print("ERROR: ZALO_TEST_USER_ID and ZALO_TEST_GROUP_NAME are required", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    remote = rf'''
set -euo pipefail
cd /opt/assistant
python3 - <<'PY'
import concurrent.futures, json, pathlib, subprocess, time, urllib.request

uid={USER_ID!r}
group_name={GROUP_NAME!r}.casefold()
tag=str(int(time.time()))

def post(path,payload):
    req=urllib.request.Request(
        "http://127.0.0.1:8787"+path,
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={{"Content-Type":"application/json"}},method="POST")
    return json.loads(urllib.request.urlopen(req,timeout=25).read().decode() or "{{}}")

def allowed_group():
    rows=[]
    path=pathlib.Path("/data/assistant/zalo_allowed_threads.txt")
    for raw in path.read_text(encoding="utf-8",errors="replace").splitlines():
        line=raw.strip()
        if not line or line.startswith("#"):
            continue
        ident,sep,name=line.partition("|")
        if sep and name.strip().casefold()==group_name:
            rows.append(ident.strip())
    if len(rows)!=1:
        raise SystemExit("FAIL_GROUP_RESOLUTION")
    return rows[0]

health=json.loads(urllib.request.urlopen("http://127.0.0.1:8787/health",timeout=8).read().decode() or "{{}}")
own=str(health.get("ownId") or "")
if not health.get("loggedIn") or int(health.get("sseClients") or 0)!=1 or not own:
    raise SystemExit("FAIL_BRIDGE_HEALTH")

group_id=allowed_group()
destinations=((uid,"user"),(group_id,"group"))

def seed(thread_id,thread_type):
    result=post("/send",{{
        "threadId":thread_id,"threadType":thread_type,
        "text":"The city established for this conversation is Hue.",
    }})
    root=result.get("result") if isinstance(result,dict) else {{}}
    root=root if isinstance(root,dict) else {{}}
    message=root.get("message") if isinstance(root.get("message"),dict) else {{}}
    value=str(message.get("msgId") or root.get("msgId") or "")
    if not value:
        raise RuntimeError("missing seed acknowledgement")
    return {{
        "msgType":str(message.get("msgType") or "webchat"),
        "msgId":value,
        "cliMsgId":str(message.get("cliMsgId") or value),
        "content":str(message.get("content") or "The city established for this conversation is Hue."),
        "ownerId":own,"uidFrom":str(message.get("uidFrom") or own),
        "ts":str(message.get("ts") or ""),"ttl":message.get("ttl") or 0,
    }}

seeds={{thread_type:seed(thread_id,thread_type) for thread_id,thread_type in destinations}}
started=time.time()

cases=(
    ("one","What is six times seven? Answer briefly."),
    ("two","According to the message I quoted, which city was established? Answer briefly."),
    ("three","What city are we discussing now? Answer briefly."),
    ("four","What is seven plus five? Answer briefly."),
)

def inject_burst(thread_id,thread_type):
    accepted=[]
    request_ids=[]
    expected_quotes=[]
    sent_cases=[]
    for index,(label,text) in enumerate(cases):
        scoped_text=text
        request_id="burst-"+thread_type+"-"+label+"-"+tag
        payload={{
            "threadId":thread_id,"threadType":thread_type,"senderId":uid,
            "senderName":"test-user","messageId":request_id,
            "text":scoped_text,"isSelf":False,
        }}
        expected_quote=request_id
        if index==1:
            quote=dict(seeds[thread_type])
            payload.update({{"quote":quote,"quoted":quote,"quotedOwnerId":own}})
            expected_quote=str(quote["msgId"])
        if thread_type=="group":
            payload["mentions"]=[own]
        accepted.append(bool(post("/inject-event",{{"type":"message","payload":payload}}).get("ok")))
        request_ids.append(request_id)
        if index==1:
            expected_quotes.append(expected_quote)
        sent_cases.append((label,scoped_text))
    return accepted,request_ids,expected_quotes,sent_cases

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    futures={{tt:pool.submit(inject_burst,tid,tt) for tid,tt in destinations}}
    burst={{tt:future.result() for tt,future in futures.items()}}
if not all(all(row[0]) for row in burst.values()):
    raise SystemExit("FAIL_ADMISSION")

def history_rows(thread_id,thread_type,event):
    sql=(
        "select coalesce(content,'') from zalo_message_history "
        "where thread_id='"+thread_id+"' and thread_type='"+thread_type+"' "
        "and event='"+event+"' and created_at>=to_timestamp("+repr(started)+") order by id"
    )
    raw=subprocess.check_output(
        ["docker","exec","postgres","sh","-lc",'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc '+json.dumps(sql)],
        text=True,errors="replace")
    return raw.splitlines()

def result_rows(thread_id,thread_type):
    sql=(
        "select coalesce(meta->>'source_message_id','')||chr(9)||coalesce(content,'') "
        "from zalo_message_history where thread_id='"+thread_id+"' and thread_type='"+thread_type+"' "
        "and event='delivered' and coalesce(meta->>'delivery_kind','result')='result' "
        "and created_at>=to_timestamp("+repr(started)+") order by id"
    )
    raw=subprocess.check_output(
        ["docker","exec","postgres","sh","-lc",'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc '+json.dumps(sql)],
        text=True,errors="replace")
    rows=[]
    for line in raw.splitlines():
        source_id,sep,content=line.partition("\t")
        if sep:
            rows.append((source_id,content))
    return rows

def user_turn_ids(thread_id,thread_type):
    sql=(
        "select coalesce(message_id,'') from zalo_message_history "
        "where thread_id='"+thread_id+"' and thread_type='"+thread_type+"' "
        "and event='user_turn' and created_at>=to_timestamp("+repr(started)+") order by id"
    )
    raw=subprocess.check_output(
        ["docker","exec","postgres","sh","-lc",'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc '+json.dumps(sql)],
        text=True,errors="replace")
    return [row for row in raw.splitlines() if row]

def queue_active_count():
    valkey=subprocess.check_output(
        ["docker","ps","--filter","label=com.docker.compose.service=valkey","--format","{{{{.Names}}}}"],
        text=True).splitlines()[0]
    raw=subprocess.check_output(
        ["docker","exec",valkey,"valkey-cli","--raw","SCARD","assistant:gate:qactive"],
        text=True).strip()
    return int(raw or "0"),valkey

deadline=time.time()+300
delivered={{}}
while time.time()<deadline:
    complete=queue_active_count()[0]==0
    for thread_id,thread_type in destinations:
        request_ids=burst[thread_type][1]
        rows=result_rows(thread_id,thread_type)
        current=[(source_id,content) for source_id,content in rows if source_id in request_ids]
        delivered[thread_type]=current
        if [source_id for source_id,_content in current] != request_ids:
            complete=False
        if len(history_rows(thread_id,thread_type,"processing"))<4:
            complete=False
    if complete:
        break
    time.sleep(3)
else:
    raise SystemExit("FAIL_TERMINAL_DELIVERY")

for thread_id,thread_type in destinations:
    request_ids=burst[thread_type][1]
    current=[message_id for message_id in user_turn_ids(thread_id,thread_type) if message_id in request_ids]
    if current != request_ids:
        raise SystemExit("FAIL_SESSION_USER_PAIRING")

names=subprocess.check_output(["docker","ps","--format","{{{{.Names}}}}"],text=True).splitlines()
dispatcher=next((name for name in names if name.startswith("assistant-dispatcher-")),"")
if not dispatcher:
    raise SystemExit("FAIL_NO_SEMANTIC_EVALUATOR")
judge_input={{"dm":[content for _source,content in delivered["user"]],
             "group":[content for _source,content in delivered["group"]]}}
judge_code="""
import json, os, urllib.request
responses="""+repr(judge_input)+"""
prompt=(
    "Evaluate two ordered chat response lists, one DM and one group. Ignore short queue/status notices. "
    "For each list decide whether terminal answers, in order, (1) answer forty-two to six times seven, "
    "(2) answer Hue from an explicit quoted message, (3) retain Hue in a contextual follow-up, and "
    "(4) answer twelve to an unrelated arithmetic question. Also require no unnecessary clarification and no "
    "cross-conversation content. Return JSON only with keys dm and group; each value must contain four boolean "
    "case_results, boolean fifo_semantics, and integer quality_score from 1 to 10.\\nDATA="+json.dumps(responses)
)
body=json.dumps({{"model":"classifier","stream":False,"max_tokens":300,
                 "messages":[{{"role":"user","content":prompt}}]}}).encode()
base=(os.environ.get("OMNIROUTER_BASE_URL") or "http://omni-router:20129/v1").rstrip("/")
key=(os.environ.get("OMNIROUTER_API_KEY") or "").strip()
request=urllib.request.Request(base+"/chat/completions",data=body,method="POST",
    headers={{"Authorization":"Bearer "+key,"Content-Type":"application/json"}})
with urllib.request.urlopen(request,timeout=180) as response:
    data=json.loads(response.read().decode() or "{{}}")
message=((data.get("choices") or [{{}}])[0].get("message") or {{}})
content=(message.get("content") or message.get("reasoning_content") or "").strip()
start=content.find("{{"); end=content.rfind("}}")
if start<0 or end<start: raise SystemExit(3)
print(content[start:end+1])
"""
judged=None
for _attempt in range(3):
    judged=subprocess.run(["docker","exec","-i",dispatcher,"python3","-"],input=judge_code,
        text=True,capture_output=True,timeout=210)
    if judged.returncode==0:
        break
    low=((judged.stderr or "")+(judged.stdout or "")).casefold()
    if any(word in low for word in ("quota","rate limit","429","free model")):
        raise SystemExit("SKIP_SEMANTIC_EVALUATOR_QUOTA")
if judged is None or judged.returncode!=0:
    diagnostic=((judged.stderr or "")+(judged.stdout or ""))[-600:] if judged is not None else "missing result"
    print("SEMANTIC_EVALUATOR_DIAGNOSTIC "+json.dumps({{
        "returncode": judged.returncode if judged is not None else None,
        "detail": diagnostic,
    }}))
    raise SystemExit("FAIL_SEMANTIC_EVALUATOR")
try:
    evaluation=json.loads((judged.stdout or "").strip())
except json.JSONDecodeError:
    raise SystemExit("FAIL_SEMANTIC_EVALUATOR_FORMAT")
for key in ("dm","group"):
    row=evaluation.get(key) if isinstance(evaluation,dict) else None
    results=(row or {{}}).get("case_results")
    score=int((row or {{}}).get("quality_score") or 0)
    if not isinstance(results,list) or len(results)!=4 or not all(value is True for value in results):
        raise SystemExit("FAIL_CONTEXT_SEMANTICS")
    if (row or {{}}).get("fifo_semantics") is not True or score<7:
        raise SystemExit("FAIL_CONTEXT_QUALITY")

logs=[]
for name in names:
    if not name.startswith("assistant-hermes-"):
        continue
    result=subprocess.run(["docker","logs","--since",str(int(started)),name],text=True,capture_output=True)
    logs.append((result.stdout or "")+(result.stderr or ""))
log_text="\n".join(logs)
if "queue turn timeout" in log_text.lower():
    raise SystemExit("FAIL_LATE_TIMEOUT")

active,valkey=queue_active_count()
if active!=0:
    raise SystemExit("FAIL_QUEUE_RESIDUE")

elapsed=round(time.time()-started,2)
print(json.dumps({{
    "ok":True,"destinations":2,"messages_per_destination":4,
    "delivered":8,"fifo":True,"quoted_context":True,
    "synthetic_quote_transport_required":False,
    "context_continuity":True,"scope_isolation":True,
    "llm_self_evaluation":True,
    "queue_empty":True,"late_timeout":False,"elapsed_s":elapsed,
}},separators=(",",":")))
PY
'''
    client = connect()
    try:
        raw = sanitize(sudo_bash(client, remote, timeout=420) or "")
    finally:
        client.close()
    line = next((row for row in reversed(raw.splitlines()) if row.startswith("{")), "")
    try:
        result = json.loads(line)
    except json.JSONDecodeError:
        result = {"ok": False, "error": "missing_result"}
    report = {"timestamp": timestamp(), "result": result}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
