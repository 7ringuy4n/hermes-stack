# -*- coding: utf-8 -*-
"""Lab: 4-item English Zalo lá»‹ch in 2 minutes. Watch plugin for 4 replies.

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
from deploy_stack import connect, sudo_bash  # noqa: E402
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode() or "{{}}")

home = (os.environ.get("ZALO_HOME_CHANNEL") or "").strip()
thread_id = ""
thread_type = "user"
sender_id = ""
admin_id = ""
for path in (
    "/data/assistant/zalo_admin_users.txt",
    "/opt/data/zalo_admin_users.txt",
):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        continue
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        tid, _, _label = raw.partition("|")
        tid = tid.strip()
        if tid:
            admin_id = tid
            break
    if admin_id:
        break
if admin_id:
    thread_id = admin_id
    thread_type = "user"
    sender_id = admin_id
elif home:
    if ":" in home:
        prefix, _, rest = home.partition(":")
        if prefix.strip().lower() == "user":
            thread_type = "user"
            thread_id = rest.strip()
        elif prefix.strip().lower() == "group":
            raise SystemExit("NO_ADMIN_DM")
        else:
            thread_id = home
            thread_type = "user"
    else:
        thread_id = home
        thread_type = "user"
    sender_id = thread_id
if not thread_id:
    raise SystemExit("NO_ADMIN_DM")
print(f"DEST thread_type={{thread_type}} tid_len={{len(thread_id)}} admin_dm=1")
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
        "chat_type": "dm",
        "sender_id": sender_id,
        "sender_name": sender_id,
        "execute": "hermes",
    }},
}}
got = post("http://127.0.0.1:8108/v1/schedules", body)
sch = got.get("schedule") or {{}}
ctx = sch.get("context") if isinstance(sch.get("context"), dict) else {{}}
plan = ctx.get("plan") if isinstance(ctx.get("plan"), dict) else {{}}
inst = plan.get("instructions") if isinstance(plan.get("instructions"), list) else []
print("UPSERT", got.get("ok"), sch.get("id"), sch.get("cron_expr"), sch.get("next_run_at"))
print("PLAN_HINT", plan.get("task_hint"), "PLAN_N", len(inst), "CADENCE", sch.get("cadence"))
PY
echo CREATE_DONE
""",
            timeout=240,
        )
        print(_sanitize(apply[-1500:]), flush=True)
        if "CREATE_DONE" not in apply or "NO_ADMIN_DM" in apply or "NO_THREAD" in apply:
            print("FAIL create", flush=True)
            return 1
        if "PLAN_N 4" not in apply:
            print("FAIL classify did not persist 4 instructions", flush=True)
            return 1

        wait_s = int((fire_local - datetime.now(TZ)).total_seconds()) + 15
        print(f"[{ts()}] waiting {wait_s}s until fire + buffer", flush=True)
        time.sleep(max(5, wait_s))

        print(f"[{ts()}] watching plugin / workflow up to {WAIT_AFTER_FIRE_S}s", flush=True)
        since_iso = (fire_local.astimezone(timezone.utc) - timedelta(seconds=45)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        fire_pg = fire_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00")
        watch_sh = r"""
set -euo pipefail
deadline=$(( $(date +%s) + __WAIT__ ))
echo "WATCH_START $(date -Is) since=__SINCE__ fire=__FIRE__"
set +e
cd /opt/assistant
set -a; . ./.env; set +a
PGUSER="${MEMORY_DB_USER:-hermes}"
PGDB="${MEMORY_DB_NAME:-hermes_memory}"
export PGPASSWORD="${MEMORY_DB_PASSWORD:-}"
since="__SINCE__"
hermes_logs() {
  docker ps --filter name=hermes --filter status=running --format '{{.Names}}' | while read -r n; do
    docker logs --since "$since" "$n" 2>&1
  done
}
done_n=0
attach_n=0
extra_after_done=0
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
print("sched_present", bool(sch), "fired", bool(sch and sch.get("last_fired_at")), "next", (sch or {}).get("next_run_at"))
PY
  docker exec -e PGPASSWORD="$PGPASSWORD" postgres psql -U "$PGUSER" -d "$PGDB" -Atc "
SELECT 'wf='||w.id||' status='||w.status||' jobs='||count(j.id)||' done='||count(*) FILTER (WHERE j.status='COMPLETED')||' run='||count(*) FILTER (WHERE j.status='RUNNING')
FROM wf.workflows w JOIN wf.jobs j ON j.workflow_id=w.id
WHERE w.origin->>'test'='case25' AND w.created_at >= TIMESTAMPTZ '__FIRE__'
GROUP BY w.id, w.status
ORDER BY w.created_at DESC LIMIT 3;
" 2>/dev/null || true
  logs=$(hermes_logs | grep -E '\[zalo\] workflow job done|send-attachment path|send-attachment fail|workflow job failed|Zalo: drop send|skip autosend' | tail -20)
  echo "LOGS_N=$(printf '%s\n' "$logs" | grep -c . || true)"
  printf '%s\n' "$logs" | tail -10
  done_n=$(hermes_logs | grep -c '\[zalo\] workflow job done' || true)
  attach_n=$(hermes_logs | grep -c 'send-attachment path' || true)
  attach_mp4=$(hermes_logs | grep -c 'send-attachment path.*\.mp4' || true)
  echo "done_jobs=$done_n attach=$attach_n attach_mp4=$attach_mp4"
  find /data/assistant/media/out -name '*.mp4' -newermt "$since" -printf 'NEW_MP4 %T+ %p\n' 2>/dev/null | tail -5 || true
  if [ "${done_n:-0}" -ge 4 ] && [ "${attach_n:-0}" -ge 1 ] && [ "${attach_mp4:-0}" -ge 1 ]; then
    echo "FOUR_JOBS_DONE"
    echo "MEDIA_SENT"
    echo "VIDEO_SENT"
    break
  fi
  if [ "${done_n:-0}" -ge 4 ]; then
    extra_after_done=$((extra_after_done + 1))
    echo "jobs_complete extra_poll=$extra_after_done"
    if [ "$extra_after_done" -ge 4 ]; then
      echo "FOUR_JOBS_DONE"
      if [ "${attach_n:-0}" -ge 1 ]; then echo "MEDIA_SENT"; fi
      echo "VIDEO_MISSING"
      break
    fi
  fi
  sleep 15
done
echo "WATCH_END $(date -Is) done_jobs=$done_n attach=$attach_n"
docker exec -e PGPASSWORD="$PGPASSWORD" postgres psql -U "$PGUSER" -d "$PGDB" -c "
SELECT j.seq, left(j.instruction,80) AS instr, j.status, left(coalesce(j.error,''),40) AS err
FROM wf.workflows w JOIN wf.jobs j ON j.workflow_id=w.id
WHERE w.origin->>'test'='case25' AND w.created_at >= TIMESTAMPTZ '__FIRE__'
ORDER BY w.created_at DESC, j.seq
LIMIT 8;
" 2>/dev/null || true
echo WATCH_DONE
"""
        watch_sh = (
            watch_sh.replace("__WAIT__", str(WAIT_AFTER_FIRE_S))
            .replace("__SID__", SID)
            .replace("__SINCE__", since_iso)
            .replace("__FIRE__", fire_pg)
        )
        watch = sudo_bash(
            c,
            watch_sh,
            timeout=WAIT_AFTER_FIRE_S + 90,
        )
        print(_sanitize(watch[-4000:]), flush=True)
        (OUT / "watch.txt").write_text(_sanitize(watch), encoding="utf-8")
        four = "FOUR_JOBS_DONE" in watch or "done_jobs=4" in watch
        media = "MEDIA_SENT" in watch
        video = "VIDEO_SENT" in watch
        if not media:
            for line in reversed(watch.splitlines()):
                if "attach=" in line:
                    raw = line.rsplit("attach=", 1)[-1].split()[0]
                    try:
                        media = int(raw) >= 1
                    except ValueError:
                        media = False
                    break
        if not video:
            for line in reversed(watch.splitlines()):
                if "attach_mp4=" in line:
                    raw = line.rsplit("attach_mp4=", 1)[-1].split()[0]
                    try:
                        video = int(raw) >= 1
                    except ValueError:
                        video = False
                    break
        if four and not media:
            print("FAIL media created but not sent (attach=0)", flush=True)
        if four and media and not video:
            print("FAIL video not sent (no send-attachment mp4 in fire window)", flush=True)
        ok = four and media and video
        summary = [
            "# Case 25 Zalo special four",
            "",
            f"- Time: `{ts()}`",
            f"- Fire local: `{fire_local.strftime('%H:%M')} GMT+7`",
            f"- Four jobs done: **{'yes' if four else 'no'}**",
            f"- Media sent: **{'yes' if media else 'no'}**",
            f"- Video sent: **{'yes' if video else 'no'}**",
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

