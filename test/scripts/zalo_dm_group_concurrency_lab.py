#!/usr/bin/env python3
"""Live Zalo lab: concurrent real quote replies in one DM and one group.

The group is resolved by display name from durable channel state. Numeric
identities are supplied at runtime and never written to the report.
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
OUT = ROOT / "test" / "reports" / "run-zalo-dm-group-concurrency"
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
import concurrent.futures, json, pathlib, subprocess, time, urllib.parse, urllib.request

uid={USER_ID!r}
group_name={GROUP_NAME!r}.casefold()
tag=str(int(time.time()))

def post(path, payload):
    req=urllib.request.Request(
        "http://127.0.0.1:8787"+path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={{"Content-Type":"application/json"}},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode() or "{{}}")

def sent_id(result):
    root=result.get("result") if isinstance(result,dict) else {{}}
    root=root if isinstance(root,dict) else {{}}
    message=root.get("message") if isinstance(root.get("message"),dict) else {{}}
    return str(message.get("msgId") or root.get("msgId") or "")

def parse_entries(path):
    rows=[]
    for raw in pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line=raw.strip()
        if not line or line.startswith("#"):
            continue
        ident, sep, name=line.partition("|")
        rows.append((ident.strip(), name.strip() if sep else ""))
    return rows

groups=[row for row in parse_entries("/data/assistant/zalo_allowed_threads.txt") if row[1].casefold()==group_name]
if len(groups)!=1:
    raise SystemExit("FAIL_GROUP_RESOLUTION")
gid=groups[0][0]

health=json.loads(urllib.request.urlopen("http://127.0.0.1:8787/health",timeout=8).read().decode() or "{{}}")
own=str(health.get("ownId") or "")
if not health.get("loggedIn") or int(health.get("sseClients") or 0)!=1 or not own:
    raise SystemExit("FAIL_BRIDGE_HEALTH")

zalo_api=subprocess.check_output(
    ["docker","ps","--filter","label=com.docker.compose.service=zalo-api","--format","{{{{.Names}}}}"],
    text=True,
).splitlines()[0]
member_probe="""
import json, os, urllib.request
tid=os.environ["LAB_GROUP_ID"]
token=os.environ.get("ZALO_API_TOKEN","")
req=urllib.request.Request(
    "http://127.0.0.1:8100/v1/zalo/threads/"+tid+"/members",
    headers={{"Authorization":"Bearer "+token}},
)
print(json.dumps(json.loads(urllib.request.urlopen(req,timeout=10).read()),ensure_ascii=False))
"""
member_raw=subprocess.check_output(
    ["docker","exec","-e","LAB_GROUP_ID="+gid,zalo_api,"python3","-c",member_probe],
    text=True,
)
members=json.loads(member_raw).get("members") or []
member_ids={{str(row.get("zalo_user_id") or row.get("user_id") or row.get("id") or "") for row in members if isinstance(row,dict)}}
if len(members)!=3 or uid not in member_ids:
    raise SystemExit("FAIL_GROUP_MEMBERSHIP")

dm_seed="DM quote target "+tag
group_seed="Group quote target "+tag
dm_quote_id=sent_id(post("/send",{{"threadId":uid,"threadType":"user","text":dm_seed}}))
group_quote_id=sent_id(post("/send",{{"threadId":gid,"threadType":"group","text":group_seed}}))
if not dm_quote_id or not group_quote_id:
    raise SystemExit("FAIL_REAL_QUOTE_ID")

dm_marker="DM_CONCURRENCY_"+tag
group_marker="GROUP_CONCURRENCY_"+tag
started=time.time()

def inject(thread_id, thread_type, message_id, marker, quote_id, seed):
    quote={{"msgType":"webchat","msgId":quote_id,"cliMsgId":quote_id,"content":seed,"ownerId":own,"uidFrom":own}}
    payload={{"type":"message","payload":{{
        "threadId":thread_id,"threadType":thread_type,"senderId":uid,
        "senderName":"test-user","messageId":message_id,
        "text":"Reply with exactly "+marker,"isSelf":False,
        "quote":quote,"quoted":quote,"quotedOwnerId":own,
    }}}}
    return bool(post("/inject-event",payload).get("ok"))

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    futures=[
        pool.submit(inject,uid,"user","dm-"+tag,dm_marker,dm_quote_id,dm_seed),
        pool.submit(inject,gid,"group","group-"+tag,group_marker,group_quote_id,group_seed),
    ]
    accepted=[future.result() for future in futures]
if accepted != [True,True]:
    raise SystemExit("FAIL_INJECT")

deadline=time.time()+180
dm_ok=group_ok=crossed=False
while time.time()<deadline:
    journal=subprocess.check_output(
        ["journalctl","--user","-u","com.hermes.zaloplugin","--since",f"@{{int(started)}}","--no-pager","-o","cat"],
        text=True,errors="replace",
    )
    dm_ok=any(dm_marker in line and "type=user" in line and "self=true" in line for line in journal.splitlines())
    group_ok=any(group_marker in line and "type=group" in line and "self=true" in line for line in journal.splitlines())
    crossed=any(
        (dm_marker in line and "type=group" in line) or
        (group_marker in line and "type=user" in line)
        for line in journal.splitlines()
        if "self=true" in line
    )
    if dm_ok and group_ok:
        break
    time.sleep(3)

elapsed=round(time.time()-started,2)
if not dm_ok or not group_ok or crossed:
    raise SystemExit("FAIL_DELIVERY_ISOLATION")

valkey=subprocess.check_output(
    ["docker","ps","--filter","label=com.docker.compose.service=valkey","--format","{{{{.Names}}}}"],
    text=True,
).splitlines()[0]
active=subprocess.check_output(
    ["docker","exec",valkey,"valkey-cli","--raw","SMEMBERS","assistant:gate:qactive"],
    text=True,errors="replace",
).splitlines()
if uid in active or gid in active:
    raise SystemExit("FAIL_QUEUE_NOT_DRAINED")

print(json.dumps({{
    "ok":True,"requests":2,"elapsed_s":elapsed,"group_members":len(members),
    "dm_quote":True,"group_quote":True,"crossed":False,"queue_empty":True,
}},separators=(",",":")))
PY
'''
    client = connect()
    try:
        raw = sanitize(sudo_bash(client, remote, timeout=300) or "")
    finally:
        client.close()
    line = next((row for row in reversed(raw.splitlines()) if row.startswith("{")), "")
    try:
        result = json.loads(line)
    except json.JSONDecodeError:
        result = {"ok": False, "error": "missing_result"}
    report = {"timestamp": timestamp(), "result": result, "output": raw[-2000:]}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
