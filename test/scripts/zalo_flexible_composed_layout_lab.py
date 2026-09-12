# -*- coding: utf-8 -*-
"""Live Zalo gate for request-authored single-region composed-image layouts."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize  # noqa: E402

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-flexible-composed-layout"
USER_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
SCHEDULE_REQUEST = (
    "2 phút nữa vẽ cho tôi hình thời tiết Đà Nẵng hiện tại có kèm thông tin "
    "thời tiết và giá xăng ở bên dưới hình"
)
IMMEDIATE_REQUEST = (
    "vẽ cho tôi hình thời tiết Đà Nẵng hiện tại có kèm thông tin thời tiết và "
    "giá xăng cùng chung 1 khung hình bên trái"
)


def main() -> int:
    if not USER_ID:
        print("ERROR: ZALO_TEST_USER_ID is required", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    scheduled_b64 = base64.b64encode(SCHEDULE_REQUEST.encode("utf-8")).decode("ascii")
    immediate_b64 = base64.b64encode(IMMEDIATE_REQUEST.encode("utf-8")).decode("ascii")
    remote = rf'''
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
export LAB_UID={USER_ID!r}
export LAB_SCHEDULED_B64={scheduled_b64!r}
export LAB_IMMEDIATE_B64={immediate_b64!r}
python3 - <<'PY'
import base64,json,os,pathlib,re,subprocess,time,urllib.request
from datetime import datetime

uid=os.environ['LAB_UID']
scheduled=base64.b64decode(os.environ['LAB_SCHEDULED_B64']).decode()
immediate=base64.b64decode(os.environ['LAB_IMMEDIATE_B64']).decode()
tag=str(int(time.time()))
immediate_id='layout-left-'+tag
started=time.time()

def request(url, body=None, method=None, timeout=30):
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
    req=urllib.request.Request(url,data=data,method=method,headers={{'Content-Type':'application/json'}})
    return json.loads(urllib.request.urlopen(req,timeout=timeout).read() or b'{{}}')

def inject(text,message_id):
    return bool(request('http://127.0.0.1:8787/inject-event',{{
        'type':'message','threadId':uid,'threadType':'user','senderId':uid,
        'senderName':'test-user','text':text,'messageId':message_id,
    }},'POST').get('ok'))

if not inject(scheduled,'layout-schedule-'+tag):
    raise SystemExit('FAIL_SCHEDULE_ADMISSION')

schedule=None
deadline=time.time()+180
while time.time()<deadline:
    for row in request('http://127.0.0.1:8110/v1/schedules').get('schedules') or []:
        context=row.get('context') if isinstance(row.get('context'),dict) else {{}}
        if context.get('original_request')==scheduled:
            schedule=row
            break
    if schedule:
        break
    time.sleep(3)
if not schedule:
    raise SystemExit('FAIL_SCHEDULE_NOT_STORED')
sid=str(schedule.get('id') or '')
if not re.fullmatch(r'[A-Za-z0-9_-]+',sid):
    raise SystemExit('FAIL_SCHEDULE_ID')
context=schedule.get('context') if isinstance(schedule.get('context'),dict) else {{}}
plan=context.get('plan') if isinstance(context.get('plan'),dict) else {{}}
details=plan.get('task_details') if isinstance(plan.get('task_details'),list) else []
searches=[i for i,item in enumerate(details) if isinstance(item,dict) and item.get('task_type')=='search']
media=[item for item in details if isinstance(item,dict) and item.get('task_type')=='media_generation']
deps=media[0].get('depends_on') if len(media)==1 else []
if not (plan.get('task_hint')=='schedule' and len(searches)>=2 and len(media)==1 and all(i in deps for i in searches)):
    raise SystemExit('FAIL_SCHEDULE_PLAN')

if not inject(immediate,immediate_id):
    raise SystemExit('FAIL_IMMEDIATE_ADMISSION')

zalo=subprocess.check_output([
    'docker','ps','--filter','label=com.docker.compose.service=zalo-api','--format','{{{{.Names}}}}'
],text=True).splitlines()[0]
probe="""import json,os,psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as c:
 if os.environ['MODE']=='exact':
  r=c.execute(\"select coalesce(meta->>'file_name','') from zalo_message_history where event='delivered' and meta->>'attachment_kind'='image' and meta->>'source_message_id'=%s and created_at>=to_timestamp(%s) order by id desc limit 1\",(os.environ['SOURCE'],int(os.environ['STARTED']))).fetchone()
 else:
  r=c.execute(\"select coalesce(meta->>'file_name','') from zalo_message_history where event='delivered' and meta->>'attachment_kind'='image' and meta->>'source_message_id' like %s and created_at>=to_timestamp(%s) order by id desc limit 1\",('schedule:'+os.environ['SOURCE']+':%',int(os.environ['STARTED']))).fetchone()
print(json.dumps({{'file':r[0] if r else ''}}))"""

def delivered(mode,source):
    raw=subprocess.check_output([
        'docker','exec','-e','MODE='+mode,'-e','SOURCE='+source,
        '-e','STARTED='+str(int(started)),zalo,'python3','-c',probe
    ],text=True)
    return pathlib.Path(json.loads(raw).get('file') or '').name

left_file=bottom_file=''
deadline=started+540
while time.time()<deadline:
    left_file=delivered('exact',immediate_id)
    bottom_file=delivered('schedule',sid)
    if left_file and bottom_file:
        break
    time.sleep(5)
if not left_file:
    raise SystemExit('FAIL_IMMEDIATE_IMAGE')
if not bottom_file:
    raise SystemExit('FAIL_SCHEDULED_IMAGE')

paths=[pathlib.Path('/data/assistant/media/out')/name for name in (left_file,bottom_file)]
if any(not path.is_file() or path.stat().st_size<80000 for path in paths):
    raise SystemExit('FAIL_IMAGE_QUALITY_FLOOR')

logs=[]
local_start=datetime.fromtimestamp(started-5).strftime('%Y-%m-%d %H:%M:%S')
for name in subprocess.check_output(['docker','ps','--format','{{{{.Names}}}}'],text=True).splitlines():
    if not name.startswith('assistant-hermes-'):
        continue
    rid=subprocess.check_output(['docker','inspect','-f','{{{{.Config.Hostname}}}}',name],text=True).strip()
    path=pathlib.Path('/data/assistant/replicas')/rid/'logs'/'agent.log'
    if path.is_file():
        logs.extend(line for line in path.read_text(encoding='utf-8',errors='replace').splitlines() if line[:19]>=local_start)
layout='\n'.join(line for line in logs if 'composed image layout request=' in line)
model_rendered='\n'.join(line for line in logs if 'composed image rendered mode=model full_bleed=true' in line)
single_region=len(re.findall(r'panels=0',layout))>=2
left_ok=bool(re.search(r'panels=0 facts=[1-6] placement=left-column',layout))
bottom_ok=bool(re.search(r'panels=0 facts=[1-6] placement=bottom-(?:left|center|right|bar)',layout))
if not single_region:
    raise SystemExit('FAIL_REGION_GROUPING')
if not left_ok:
    raise SystemExit('FAIL_LEFT_PLACEMENT')
if not bottom_ok:
    raise SystemExit('FAIL_BOTTOM_PLACEMENT')
if len(model_rendered.splitlines())<2:
    raise SystemExit('FAIL_MODEL_RENDERED_COMPOSITION')
if '/v1/overlay' in '\n'.join(logs):
    raise SystemExit('FAIL_LEGACY_IMAGE_OVERLAY')

valkey=subprocess.check_output([
    'docker','ps','--filter','label=com.docker.compose.service=valkey','--format','{{{{.Names}}}}'
],text=True).splitlines()[0]
active=subprocess.check_output(['docker','exec',valkey,'valkey-cli','--raw','SMEMBERS','assistant:gate:qactive'],text=True).splitlines()
if uid in active:
    raise SystemExit('FAIL_QUEUE_RESIDUE')

print(json.dumps({{
    'ok':True,'requests':2,'immediate_image':True,'scheduled_image':True,
    'source_correlated':True,'single_region':True,'left_column':True,
    'bottom_region':True,'artifacts':2,'elapsed_s':round(time.time()-started,2),
}},separators=(',',':')))
PY
'''
    if (os.environ.get("ASSISTANT_TEST_LOCAL") or "").strip().casefold() in {"1", "true", "yes"}:
        completed = subprocess.run(
            ["bash", "-lc", remote], capture_output=True, text=True, timeout=840
        )
        raw = sanitize((completed.stdout or "") + (completed.stderr or ""))
    else:
        from deploy_stack import connect, sudo_bash

        client = connect()
        try:
            raw = sanitize(sudo_bash(client, remote, timeout=840) or "")
        finally:
            client.close()
    line = next((row for row in reversed(raw.splitlines()) if row.startswith("{")), "")
    try:
        result = json.loads(line)
    except json.JSONDecodeError:
        failure = next((row for row in reversed(raw.splitlines()) if row.startswith("FAIL_")), "missing_result")
        result = {"ok": False, "error": failure}
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "result": result}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
