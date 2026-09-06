#!/usr/bin/env python3
"""VPS lab: cancel active Zalo work by plain message and real quote metadata.

Environment: ASSISTANT_SSH_*, ZALO_TEST_USER_ID, optional ZALO_TEST_GROUP_NAME,
ZALO_CANCEL_MODES (`plain,quote`), ZALO_CANCEL_SCOPES (`dm,group`),
ZALO_CANCEL_DELAY_S, ZALO_CANCEL_OBSERVE_S.
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402
from sanitize import sanitize  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-active-cancel"
USER_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
MODES = [part.strip() for part in (os.environ.get("ZALO_CANCEL_MODES") or "plain,quote").split(",") if part.strip()]
SCOPES = [part.strip() for part in (os.environ.get("ZALO_CANCEL_SCOPES") or "dm,group").split(",") if part.strip()]
GROUP_NAME = (os.environ.get("ZALO_TEST_GROUP_NAME") or "test").strip()
DELAY_S = max(2, int(os.environ.get("ZALO_CANCEL_DELAY_S") or "6"))
OBSERVE_S = max(15, int(os.environ.get("ZALO_CANCEL_OBSERVE_S") or "75"))


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def run_mode(client, mode: str, scope: str) -> str:
    remote = rf'''
set -euo pipefail
cd /opt/assistant
python3 - <<'PY'
import json, pathlib, subprocess, time, urllib.request

uid={USER_ID!r}
mode={mode!r}
scope={scope!r}
group_name={GROUP_NAME!r}.casefold()
delay_s={DELAY_S}
observe_s={OBSERVE_S}
tag="cancel-"+scope+"-"+mode+"-"+str(int(time.time()))

def post(path, payload):
    request=urllib.request.Request(
        "http://127.0.0.1:8787"+path,
        data=json.dumps(payload).encode("utf-8"),
        headers={{"Content-Type":"application/json"}},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(request, timeout=20).read().decode() or "{{}}")

def history():
    sql=(
        "select coalesce(message_id,''),event,coalesce(task_hint,'') "
        "from zalo_message_history where message_id='"+tag+"' order by id"
    )
    return subprocess.check_output(
        ["docker","exec","postgres","sh","-lc",'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc '+json.dumps(sql)],
        text=True,
        errors="replace",
    )

def gateway_text():
    out=[]
    names=subprocess.check_output(["docker","ps","--format","{{{{.Names}}}}"], text=True).splitlines()
    for name in names:
        if not name.startswith("assistant-hermes-"):
            continue
        ident=subprocess.check_output(["docker","inspect","-f","{{{{.Id}}}}",name], text=True).strip()[:12]
        path=pathlib.Path("/data/assistant/replicas")/ident/"logs/gateway.log"
        if path.is_file():
            out.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)

health=json.loads(urllib.request.urlopen("http://127.0.0.1:8787/health",timeout=8).read().decode() or "{{}}")
if not health.get("loggedIn") or int(health.get("sseClients") or 0) != 1:
    raise SystemExit("FAIL_BRIDGE_HEALTH")
own=str(health.get("ownId") or "")
target=uid
thread_type="user"
if scope == "group":
    rows=[]
    for raw in pathlib.Path("/data/assistant/zalo_allowed_threads.txt").read_text(encoding="utf-8",errors="replace").splitlines():
        line=raw.strip()
        if not line or line.startswith("#"):
            continue
        ident, sep, name=line.partition("|")
        if sep and name.strip().casefold()==group_name:
            rows.append(ident.strip())
    if len(rows)!=1:
        raise SystemExit("FAIL_GROUP_RESOLUTION")
    target=rows[0]
    thread_type="group"

quote=None
if mode == "quote":
    marker="Cancellation quote target "+tag
    sent=post("/send",{{"threadId":target,"threadType":thread_type,"text":marker}})
    result=sent.get("result") if isinstance(sent,dict) else {{}}
    result=result if isinstance(result,dict) else {{}}
    message=result.get("message") if isinstance(result.get("message"),dict) else {{}}
    real_id=str(message.get("msgId") or result.get("msgId") or "")
    if not real_id:
        raise SystemExit("FAIL_REAL_QUOTE_ID")
    quote={{"msgType":"webchat","msgId":real_id,"cliMsgId":real_id,"content":marker,"ownerId":own,"uidFrom":own}}
    print("REAL_QUOTE_ID_PRESENT")

started=time.time()
request_payload={{"type":"message","payload":{{
    "threadId":target,"threadType":thread_type,"senderId":uid,"senderName":"test-user",
    "messageId":tag,"text":"Create a highly detailed cinematic landscape image and deliver it to me.","isSelf":False,
}}}}
if thread_type == "group":
    request_payload["payload"]["mentions"]=[own]
print("START",post("/inject-event",request_payload).get("ok"))
time.sleep(delay_s)
stop_payload={{"type":"message","payload":{{
    "threadId":target,"threadType":thread_type,"senderId":uid,"senderName":"test-user",
    "messageId":tag+"-stop","text":"Stop the current request.","isSelf":False,
}}}}
if quote:
    stop_payload["payload"]["quote"]=quote
    stop_payload["payload"]["quoted"]=quote
if thread_type == "group":
    stop_payload["payload"]["mentions"]=[own]
print("STOP",post("/inject-event",stop_payload).get("ok"))

deadline=time.time()+45
events=""
while time.time() < deadline:
    events=history()
    if "|cancel_requested|control" in events and "|cancelled|control" in events:
        break
    time.sleep(2)
if "|cancel_requested|control" not in events or "|cancelled|control" not in events:
    print(events)
    raise SystemExit("FAIL_CANCEL_AUDIT")

time.sleep(observe_s)
logs=gateway_text()
if "guarded active request cancelled" not in logs and "active request cancelled" not in logs:
    raise SystemExit("FAIL_CANCEL_LOG")
recent=logs[logs.rfind("Zalo: guarded active request cancelled"):]
if "scene_image_shortcut" in recent and tag in recent:
    raise SystemExit("FAIL_LATE_IMAGE_FLOW")
print(events.strip())
print("PASS_CANCEL_"+scope.upper()+"_"+mode.upper())
PY
'''
    return sudo_bash(client, remote, timeout=OBSERVE_S + 150)


def main() -> int:
    if not USER_ID:
        print("ERROR: ZALO_TEST_USER_ID is required", file=sys.stderr)
        return 2
    if not MODES or any(mode not in {"plain", "quote"} for mode in MODES):
        print("ERROR: ZALO_CANCEL_MODES must contain plain and/or quote", file=sys.stderr)
        return 2
    if not SCOPES or any(scope not in {"dm", "group"} for scope in SCOPES):
        print("ERROR: ZALO_CANCEL_SCOPES must contain dm and/or group", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    rows=[]
    client=connect()
    try:
        for scope in SCOPES:
            for mode in MODES:
                raw=sanitize(run_mode(client, mode, scope) or "")
                marker="PASS_CANCEL_"+scope.upper()+"_"+mode.upper()
                passed=marker in raw and "FAIL_" not in raw
                rows.append({"scope":scope,"mode":mode,"ok":passed,"output":raw[-3000:]})
                print(raw, flush=True)
                if not passed:
                    break
            if rows and not rows[-1]["ok"]:
                break
    finally:
        client.close()
    ok=len(rows)==len(MODES)*len(SCOPES) and all(row["ok"] for row in rows)
    (OUT/"summary.json").write_text(json.dumps({"ok":ok,"ts":timestamp(),"rows":rows},indent=2)+"\n",encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
