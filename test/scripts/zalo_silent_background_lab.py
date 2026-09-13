#!/usr/bin/env python3
"""Real-channel scheduled research must store notes without a fire response."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash
from sanitize import sanitize

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    uid = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
    if not uid:
        raise SystemExit("ZALO_TEST_USER_ID required")
    remote = r'''
set -euo pipefail
cd /opt/assistant
export LAB_UID=__UID__
python3 - <<'PY'
import json,os,subprocess,time,urllib.request,urllib.error
uid=os.environ['LAB_UID']; started=time.time(); marker='silent-notes-'+str(int(started))
text='1 phút nữa tìm thông tin thời tiết Hồ Chí Minh hiện tại trên web và ghi chú lại'
def api(path,body=None,method=None):
 data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
 req=urllib.request.Request('http://127.0.0.1:'+path,data=data,method=method,headers={'Content-Type':'application/json'})
 return json.loads(urllib.request.urlopen(req,timeout=30).read() or '{}')
zalo=subprocess.check_output(['docker','ps','--filter','label=com.docker.compose.service=zalo-api','--format','{{.Names}}'],text=True).splitlines()[0]
probe="""import json,os,psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as c:
 notes=c.execute('SELECT id,title,content FROM notes WHERE active AND scope_id=%s AND created_at>=to_timestamp(%s)',('zalo:user:'+os.environ['UID'],float(os.environ['START']))).fetchall()
 delivered=c.execute("SELECT count(*) FROM zalo_message_history WHERE event='delivered' AND meta->>'source_message_id' LIKE %s AND created_at>=to_timestamp(%s)",('schedule:'+os.environ['SID']+':%',float(os.environ['START']))).fetchone()[0]
print(json.dumps({'notes':notes,'delivered':delivered},ensure_ascii=False))"""
def evidence(sid):
 return json.loads(subprocess.check_output(['docker','exec','-e','UID='+uid,'-e','START='+str(started),'-e','SID='+sid,zalo,'python3','-c',probe],text=True))
print('running test case 1/3: schedule admission and default silence',flush=True)
assert api('8787/inject-event',{'type':'message','threadId':uid,'threadType':'user','senderId':uid,'senderName':'test-user','text':text,'messageId':marker},'POST').get('ok')
row=None; deadline=time.time()+150
while time.time()<deadline:
 for item in api('8110/v1/schedules').get('schedules') or []:
  context=item.get('context') or {}
  if context.get('original_request')==text:
   row=item; break
 if row: break
 time.sleep(3)
assert row, 'schedule not stored'
sid=row['id']; plan=(row.get('context') or {}).get('plan') or {}
try:
 assert plan.get('persist_gathered_notes') is True, 'gather-note contract missing'
 assert plan.get('notify_on_fire') is False, 'stored-note background must default silent'
 assert not evidence(sid)['notes'], 'inner work ran during schedule creation'
 print('running test case 2/3: due research stores useful titled notes',flush=True)
 deadline=time.time()+420; result=None
 while time.time()<deadline:
  result=evidence(sid)
  if result['notes']: break
  time.sleep(5)
 assert result and result['notes'], 'scheduled note never persisted'
 assert all(n[1] and n[2] for n in result['notes']), 'missing title/content'
 assert any('http' in n[2] for n in result['notes']), 'missing research source citation'
 print('running test case 3/3: no fire delivery after note persistence',flush=True)
 time.sleep(15)
 assert evidence(sid)['delivered']==0, 'silent task sent a fire response'
 print(json.dumps({'ok':True,'checks':3,'notes':len(result['notes']),'fire_deliveries':0},separators=(',',':')),flush=True)
finally:
 try:
  api('8110/v1/schedules/'+sid,method='DELETE')
 except urllib.error.HTTPError as exc:
  if exc.code != 404: raise
PY
'''.replace("__UID__", json.dumps(uid))
    client = connect()
    try:
        try:
            output = sanitize(sudo_bash(client, remote, timeout=660))
        except SystemExit as exc:
            output = sanitize(str(exc))
    finally:
        client.close()
    out = ROOT / "test" / "reports" / "run-zalo-silent-background"
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.log").write_text(output, encoding="utf-8")
    return 0 if '"ok":true' in output else 1


if __name__ == "__main__":
    raise SystemExit(main())
