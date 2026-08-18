# -*- coding: utf-8 -*-
"""Lab: 4-item English Zalo lịch in 2 minutes. Watch plugin for 4 replies.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Reports: test/reports/run-zalo-special-four/ (no host/account)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_high import connect, sudo_bash  # noqa: E402
from sanitize import sanitize as _sanitize  # noqa: E402

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-special-four"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
SID = "case25_special_four"
WAIT_AFTER_FIRE_S = int(os.environ.get("ZALO_SPECIAL_WAIT_S", "540"))

TEXT = """1. Send a hello greeting message.
2. Draw an image of Ho Chi Minh City based on the actual current weather.
3. Give a brief update of the latest E5 RON92 and E10 RON95 gasoline prices, in Vietnamese.
4. Draw a video of Ho Chi Minh City based on the actual current weather."""


def ts() -> str:
    return datetime.now(timezone.utc).astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S %z")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        print(f"[{ts()}] probe plugin + home thread", flush=True)
        probe = sudo_bash(
            c,
            r"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
echo "HOME=${ZALO_HOME_CHANNEL:-}"
echo "=== plugin ==="
curl -sS -m 8 http://127.0.0.1:8787/health || curl -sS -m 8 http://127.0.0.1:8100/health || true
echo
echo "=== schedules_origin ==="
curl -sS -m 8 http://127.0.0.1:8108/v1/schedules | python3 -c '
import json,sys
d=json.load(sys.stdin)
for s in (d.get("schedules") or []):
    o=s.get("origin") if isinstance(s.get("origin"), dict) else {}
    ctx=s.get("context") if isinstance(s.get("context"), dict) else {}
    print("id", s.get("id"), "plat", o.get("platform"), "tid", o.get("thread_id") or ctx.get("thread_id"), "tt", o.get("thread_type") or ctx.get("thread_type"), "sid", ctx.get("sender_id"))
'
echo "=== files ==="
head -n 5 /data/assistant/zalo_allowed_threads.txt 2>/dev/null || true
head -n 5 /opt/data/zalo_allowed_threads.txt 2>/dev/null || true
echo PROBE_DONE
""",
            timeout=60,
        )
        print(_sanitize(probe[-2500:]), flush=True)
        if "PROBE_DONE" not in probe:
            print("FAIL probe", flush=True)
            return 1

        fire_local = datetime.now(TZ) + timedelta(minutes=2)
        fire_local = fire_local.replace(second=0, microsecond=0)
        # If we are already past :xx seconds, +2 min floor to minute can be < 90s; keep at least 90s.
        if (fire_local - datetime.now(TZ)).total_seconds() < 90:
            fire_local = fire_local + timedelta(minutes=1)
        cron = f"{fire_local.minute} {fire_local.hour} * * *"
        nxt = fire_local.astimezone(timezone.utc).isoformat()
        print(f"[{ts()}] schedule fire_local={fire_local.strftime('%H:%M')} cron={cron}", flush=True)

        apply = sudo_bash(
            c,
            rf"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, os, urllib.request
from pathlib import Path

text = {TEXT!r}
sid = {SID!r}
cron = {cron!r}
nxt = {nxt!r}

def get(url):
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode() or "{{}}")

def post(url, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={{"Content-Type":"application/json"}})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode() or "{{}}")

home = (os.environ.get("ZALO_HOME_CHANNEL") or "").strip()
thread_id = ""
thread_type = "user"
sender_id = ""
if home:
    if ":" in home:
        prefix, _, rest = home.partition(":")
        if prefix.strip().lower() in {{"user", "group"}}:
            thread_type = prefix.strip().lower()
            thread_id = rest.strip()
        else:
            thread_id = home
            thread_type = "user"
    else:
        thread_id = home
        thread_type = "user"
    sender_id = thread_id
if not thread_id:
    sched = get("http://127.0.0.1:8108/v1/schedules")
    for s in reversed(sched.get("schedules") or []):
        o = s.get("origin") if isinstance(s.get("origin"), dict) else {{}}
        ctx = s.get("context") if isinstance(s.get("context"), dict) else {{}}
        if str(o.get("platform") or "") != "zalo":
            continue
        tid = str(o.get("thread_id") or ctx.get("thread_id") or "").strip()
        if tid and "::job::" not in tid:
            thread_id = tid
            thread_type = str(o.get("thread_type") or ctx.get("thread_type") or "user")
            sender_id = str(o.get("user_id") or ctx.get("sender_id") or tid)
            break
if not thread_id:
    raise SystemExit("NO_THREAD")
print(f"DEST thread_type={{thread_type}} tid_len={{len(thread_id)}}")
# Drop leftover test id if re-run
try:
    urllib.request.urlopen(urllib.request.Request(
        f"http://127.0.0.1:8108/v1/schedules/{{sid}}", method="DELETE"
    ), timeout=8)
except Exception:
    pass
body = {{
    "id": sid,
    "name": "case25-special-four",
    "cron_expr": cron,
    "time": "",
    "timezone": "Asia/Ho_Chi_Minh",
    "text": text,
    "next_run_at": nxt,
    "enabled": True,
    "origin": {{
        "platform": "zalo",
        "thread_id": thread_id,
        "thread_type": thread_type,
        "user_id": sender_id,
        "chat_id": thread_id,
        "test": "case25",
    }},
    "context": {{
        "thread_id": thread_id,
        "thread_type": thread_type,
        "chat_type": "group" if thread_type == "group" else "dm",
        "sender_id": sender_id,
        "sender_name": sender_id,
        "execute": "hermes",
    }},
}}
got = post("http://127.0.0.1:8108/v1/schedules", body)
sch = got.get("schedule") or {{}}
print("UPSERT", got.get("ok"), sch.get("id"), sch.get("cron_expr"), sch.get("next_run_at"))
print("TEXT_ITEMS", text.count(chr(10))+1)
PY
echo CREATE_DONE
""",
            timeout=60,
        )
        print(_sanitize(apply[-1500:]), flush=True)
        if "CREATE_DONE" not in apply or "NO_THREAD" in apply:
            print("FAIL create", flush=True)
            return 1

        wait_s = int((fire_local - datetime.now(TZ)).total_seconds()) + 15
        print(f"[{ts()}] waiting {wait_s}s until fire + buffer", flush=True)
        time.sleep(max(5, wait_s))

        print(f"[{ts()}] watching plugin / workflow up to {WAIT_AFTER_FIRE_S}s", flush=True)
        watch_sh = r"""
set -euo pipefail
deadline=$(( $(date +%s) + __WAIT__ ))
echo "WATCH_START $(date -Is)"
set +e
cd /opt/assistant
set -a; . ./.env; set +a
PGUSER="${MEMORY_DB_USER:-hermes}"
PGDB="${MEMORY_DB_NAME:-hermes_memory}"
export PGPASSWORD="${MEMORY_DB_PASSWORD:-}"
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
hermes_logs() {
  docker ps --filter name=hermes --filter status=running --format '{{.Names}}' | while read -r n; do
    docker logs --since "$since" "$n" 2>&1
  done
}
done_n=0
attach_n=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  curl -sS -m 5 http://127.0.0.1:8787/health 2>/dev/null | python3 -c 'import sys,json
try:
 d=json.load(sys.stdin); print("plugin loggedIn", d.get("loggedIn"), "sse", d.get("sseClients"))
except Exception:
 print("plugin raw")
' || echo "plugin down"
  python3 - <<'PY'
import json, urllib.request
sid="__SID__"
try:
    d=json.loads(urllib.request.urlopen("http://127.0.0.1:8108/v1/schedules", timeout=8).read().decode() or "{}")
except Exception as e:
    print("sched_err", type(e).__name__)
    raise SystemExit(0)
sch=None
for s in (d.get("schedules") or []):
    if s.get("id")==sid:
        sch=s
        break
print("sched_fired", bool(sch and sch.get("last_fired_at")), "next", (sch or {}).get("next_run_at"))
PY
  docker exec -e PGPASSWORD="$PGPASSWORD" postgres psql -U "$PGUSER" -d "$PGDB" -Atc "
SELECT 'wf='||w.id||' status='||w.status||' jobs='||count(j.id)||' done='||count(*) FILTER (WHERE j.status='COMPLETED')||' run='||count(*) FILTER (WHERE j.status='RUNNING')
FROM wf.workflows w JOIN wf.jobs j ON j.workflow_id=w.id
WHERE w.origin->>'test'='case25'
GROUP BY w.id, w.status
ORDER BY w.created_at DESC LIMIT 3;
" 2>/dev/null || true
  logs=$(hermes_logs | grep -E '\[zalo\] workflow job done|send-attachment path|workflow job failed|Zalo: drop send' | tail -20)
  echo "LOGS_N=$(printf '%s\n' "$logs" | grep -c . || true)"
  printf '%s\n' "$logs" | tail -10
  done_n=$(hermes_logs | grep -c '\[zalo\] workflow job done' || true)
  attach_n=$(hermes_logs | grep -c 'send-attachment path' || true)
  echo "done_jobs=$done_n attach=$attach_n"
  if [ "${done_n:-0}" -ge 4 ]; then
    echo "FOUR_JOBS_DONE"
    break
  fi
  sleep 15
done
echo "WATCH_END $(date -Is) done_jobs=$done_n attach=$attach_n"
docker exec -e PGPASSWORD="$PGPASSWORD" postgres psql -U "$PGUSER" -d "$PGDB" -c "
SELECT j.seq, left(j.instruction,80) AS instr, j.status, left(coalesce(j.error,''),40) AS err
FROM wf.workflows w JOIN wf.jobs j ON j.workflow_id=w.id
WHERE w.origin->>'test'='case25'
ORDER BY w.created_at DESC, j.seq
LIMIT 8;
" 2>/dev/null || true
echo WATCH_DONE
"""
        watch_sh = watch_sh.replace("__WAIT__", str(WAIT_AFTER_FIRE_S)).replace("__SID__", SID)
        watch = sudo_bash(
            c,
            watch_sh,
            timeout=WAIT_AFTER_FIRE_S + 90,
        )
        print(_sanitize(watch[-4000:]), flush=True)
        (OUT / "watch.txt").write_text(_sanitize(watch), encoding="utf-8")
        ok = "FOUR_JOBS_DONE" in watch or "done_jobs=4" in watch
        summary = [
            "# Case 25 Zalo special four",
            "",
            f"- Time: `{ts()}`",
            f"- Fire local: `{fire_local.strftime('%H:%M')} GMT+7`",
            f"- Four jobs done: **{'yes' if ok else 'no'}**",
            "",
            "See `watch.txt`.",
            "",
        ]
        (OUT / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
        return 0 if ok else 1
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
