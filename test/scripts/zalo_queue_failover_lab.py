#!/usr/bin/env python3
"""Live Zalo lab: recover a claimed DM item after the SSE owner stops.

The test identity is runtime-only. The report contains booleans, counts, and
elapsed time, never account, group, container, queue payload, or token values.
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
OUT = ROOT / "test" / "reports" / "run-zalo-queue-failover"
USER_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def main() -> int:
    if not USER_ID:
        print("ERROR: ZALO_TEST_USER_ID is required", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    remote = rf'''
set -euo pipefail
cd /opt/assistant
python3 - <<'PY'
import json, subprocess, time, urllib.request

uid={USER_ID!r}
tag=str(int(time.time()))
marker="The silver compass is ready."

def output(*args):
    return subprocess.check_output(args,text=True,errors="replace").strip()

def containers(service):
    return output("docker","ps","--filter","label=com.docker.compose.service="+service,"--format","{{{{.Names}}}}").splitlines()

hermes=containers("hermes")
if len(hermes) != 2:
    raise SystemExit("FAIL_REPLICA_COUNT")
valkey=containers("valkey")[0]
zalo_api=containers("zalo-api")[0]

def delivered_count():
    probe="""
import os, psycopg
with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    row=conn.execute(
        "SELECT count(*) FROM zalo_message_history WHERE thread_id=%s AND thread_type='user' AND event='delivered' AND created_at >= to_timestamp(%s) AND content LIKE %s",
        (os.environ["LAB_THREAD_ID"],int(os.environ["LAB_STARTED"]),"%"+os.environ["LAB_MARKER"]+"%"),
    ).fetchone()
print(int(row[0] or 0))
"""
    value=output(
        "docker","exec","-e","LAB_THREAD_ID="+uid,"-e","LAB_MARKER="+marker,
        "-e","LAB_STARTED="+str(int(started)),
        zalo_api,"python3","-c",probe,
    )
    return int(value or "0")
lease_key="zalo:bridge:owner"
for env in json.loads(output("docker","inspect",hermes[0]))[0]["Config"]["Env"]:
    if env.startswith("ZALO_OWNER_LEASE_KEY=") and env.partition("=")[2]:
        lease_key=env.partition("=")[2]
prefix="assistant:gate"
for env in json.loads(output("docker","inspect",hermes[0]))[0]["Config"]["Env"]:
    if env.startswith("ASSISTANT_STORE_PREFIX=") and env.partition("=")[2]:
        prefix=env.partition("=")[2].rstrip(":")

lease=output("docker","exec",valkey,"valkey-cli","--raw","GET",lease_key)
owner_id=lease.partition(":")[0]
owner=""
for name in hermes:
    cid=output("docker","inspect","--format","{{{{.Id}}}}",name)
    if cid.startswith(owner_id):
        owner=name
        break
if not owner:
    raise SystemExit("FAIL_OWNER_RESOLUTION")

payload=json.dumps({{
    "kind":"part","text":"Reply with exactly this natural sentence: "+marker,
    "thread_id":uid,"thread_type":"user","sender_id":uid,
    "sender_name":"test-user","chat_type":"dm",
    "message_id":"failover-"+tag,"media_urls":[],"media_types":[],
    "message_type":"TEXT","schedule_fire":False,"plan":None,
}},ensure_ascii=False,separators=(",",":"))
q=prefix+":q:"+uid
qinflight=prefix+":qinflight:"+uid
qactive=prefix+":qactive"
qwork=prefix+":qwork:"+uid
output("docker","exec",valkey,"valkey-cli","DEL",q,qinflight,qwork)
output("docker","exec",valkey,"valkey-cli","RPUSH",qinflight,payload)
output("docker","exec",valkey,"valkey-cli","SADD",qactive,uid)
output("docker","exec",valkey,"valkey-cli","SET",qwork,"1","EX","960")

started=time.time()
subprocess.check_call(["docker","stop","-t","4",owner],stdout=subprocess.DEVNULL)
promoted=False
delivered=False
deadline=time.time()+150
while time.time()<deadline:
    try:
        current=output("docker","exec",valkey,"valkey-cli","--raw","GET",lease_key)
        promoted=bool(current and not current.startswith(owner_id+":"))
        delivered=delivered_count()==1
        if promoted and delivered:
            break
    except subprocess.CalledProcessError:
        pass
    time.sleep(3)

drain_deadline=time.time()+30
pending=inflight=0
registered=True
while time.time()<drain_deadline:
    pending=int(output("docker","exec",valkey,"valkey-cli","LLEN",q) or "0")
    inflight=int(output("docker","exec",valkey,"valkey-cli","LLEN",qinflight) or "0")
    registered=uid in output("docker","exec",valkey,"valkey-cli","--raw","SMEMBERS",qactive).splitlines()
    if pending==0 and inflight==0 and not registered:
        break
    time.sleep(1)
subprocess.check_call(["docker","start",owner],stdout=subprocess.DEVNULL)
time.sleep(12)
running=len(containers("hermes"))
health=json.loads(urllib.request.urlopen("http://127.0.0.1:8787/health",timeout=8).read().decode() or "{{}}")
ok=promoted and delivered and pending==0 and inflight==0 and not registered and running==2 and int(health.get("sseClients") or 0)==1
print(json.dumps({{
    "ok":ok,"promoted":promoted,"delivered":delivered,
    "pending":pending,"inflight":inflight,"registered":registered,
    "replicas_restored":running,"sse_clients":int(health.get("sseClients") or 0),
    "elapsed_s":round(time.time()-started,2),
}},separators=(",",":")))
if not ok:
    raise SystemExit("FAIL_QUEUE_FAILOVER")
PY
'''
    client = connect()
    try:
        raw = sanitize(sudo_bash(client, remote, timeout=240) or "")
    finally:
        client.close()
    line = next((row for row in reversed(raw.splitlines()) if row.startswith("{")), "")
    try:
        result = json.loads(line)
    except json.JSONDecodeError:
        result = {"ok": False, "error": "missing_result"}
    report = {"timestamp": timestamp(), "result": result, "output": raw[-1200:]}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
