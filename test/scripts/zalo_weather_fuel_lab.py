# -*- coding: utf-8 -*-
"""Lab: one-task HCMC weather+fuel infographic to admin DM.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Reports: test/reports/run-zalo-weather-fuel/ (no host/account)
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_fixtures import FIXTURE_INFOGRAPHIC_DAILY, FIXTURE_INFOGRAPHIC_VI  # noqa: E402
from deploy_stack import connect, sudo_bash  # noqa: E402
from sanitize import sanitize as _sanitize  # noqa: E402

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-weather-fuel"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
WAIT_S = int(os.environ.get("ZALO_INFOGRAPHIC_WAIT_S", "360"))
RUN_DAILY = os.environ.get("ZALO_INFOGRAPHIC_DAILY", "0").strip() in {"1", "true", "yes"}


def ts() -> str:
    return datetime.now(timezone.utc).astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S %z")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        print(f"[{ts()}] probe plugin", flush=True)
        probe = sudo_bash(
            c,
            r"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
echo "=== plugin ==="
curl -sS -m 8 http://127.0.0.1:8787/health || true
echo
echo PROBE_DONE
""",
            timeout=60,
        )
        print(_sanitize(probe[-1200:]), flush=True)
        if "PROBE_DONE" not in probe:
            print("FAIL probe", flush=True)
            return 1

        fire_utc = datetime.now(timezone.utc)
        fire_pg = fire_utc.strftime("%Y-%m-%d %H:%M:%S+00")
        since_iso = (fire_utc - timedelta(seconds=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[{ts()}] classify + create one-job workflow", flush=True)
        apply = sudo_bash(
            c,
            rf"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, os, urllib.request
from pathlib import Path

text = {FIXTURE_INFOGRAPHIC_VI!r}
daily = {FIXTURE_INFOGRAPHIC_DAILY!r}

def post(url, body, timeout=120):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={{"Content-Type":"application/json"}})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{{}}")

def classify(blob):
    return post("http://127.0.0.1:8096/v1/classify", {{"text": blob, "timezone": "Asia/Ho_Chi_Minh"}}, 120)

now = classify(text)
inst = now.get("instructions") if isinstance(now.get("instructions"), list) else []
print("CLASSIFY_NOW HINT", now.get("task_hint"), "PLAN_N", len(inst), "OK", now.get("ok"))
day = classify(daily)
dinst = day.get("instructions") if isinstance(day.get("instructions"), list) else []
print("CLASSIFY_DAILY HINT", day.get("task_hint"), "PLAN_N", len(dinst), "CRON", day.get("cron_expr"), "CADENCE", day.get("cadence"))
if not now.get("ok") or len(inst) != 1:
    raise SystemExit("BAD_NOW_PLAN")
if str(now.get("task_hint") or "") == "schedule":
    raise SystemExit("NOW_MUST_NOT_BE_SCHEDULE")
if not day.get("ok") or str(day.get("task_hint") or "") != "schedule" or len(dinst) != 1:
    raise SystemExit("BAD_DAILY_PLAN")

admin_id = ""
for path in ("/data/assistant/zalo_admin_users.txt", "/opt/data/zalo_admin_users.txt"):
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
if not admin_id:
    raise SystemExit("NO_ADMIN_DM")
print("DEST thread_type=user tid_len=%s admin_dm=1" % len(admin_id))
body = {{
    "instructions": inst,
    "sequential": False,
    "wrap": True,
    "origin": {{
        "platform": "zalo",
        "thread_id": admin_id,
        "thread_type": "user",
        "user_id": admin_id,
        "chat_id": admin_id,
        "test": "case26",
    }},
    "context": {{
        "thread_id": admin_id,
        "thread_type": "user",
        "chat_type": "dm",
        "sender_id": admin_id,
        "sender_name": admin_id,
        "execute": "hermes",
        "plan": now,
    }},
}}
got = post("http://127.0.0.1:8108/v1/workflows", body, 30)
wf = got.get("workflow") or {{}}
jobs = wf.get("jobs") if isinstance(wf.get("jobs"), list) else []
print("WF", got.get("ok"), wf.get("id"), "JOBS", len(jobs))
if not got.get("ok") or len(jobs) != 1:
    raise SystemExit("BAD_WF")
print("CREATE_DONE")
PY
echo CREATE_OK
""",
            timeout=180,
        )
        print(_sanitize(apply[-2500:]), flush=True)
        if "CREATE_OK" not in apply or "NO_ADMIN_DM" in apply:
            print("FAIL create", flush=True)
            return 1
        if "BAD_NOW_PLAN" in apply or "PLAN_N 1" not in apply:
            print("FAIL classify exploded or missing PLAN_N 1", flush=True)
            return 1
        if "NOW_MUST_NOT_BE_SCHEDULE" in apply:
            print("FAIL infographic classified as schedule", flush=True)
            return 1
        if "BAD_DAILY_PLAN" in apply:
            print("FAIL daily wrapper was not schedule + PLAN_N 1", flush=True)
            return 1
        if "BAD_WF" in apply:
            print("FAIL workflow was not 1 job", flush=True)
            return 1

        print(f"[{ts()}] watching up to {WAIT_S}s", flush=True)
        watch_sh = r"""
set +e
deadline=$(( $(date +%s) + __WAIT__ ))
echo "WATCH_START $(date -Is) since=__SINCE__ fire=__FIRE__"
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
while [ "$(date +%s)" -lt "$deadline" ]; do
  curl -sS -m 5 http://127.0.0.1:8787/health 2>/dev/null | python3 -c 'import sys,json
try:
 d=json.load(sys.stdin); print("plugin loggedIn", d.get("loggedIn"), "sse", d.get("sseClients"))
except Exception:
 print("plugin raw")
' || echo "plugin down"
  docker exec -e PGPASSWORD="$PGPASSWORD" postgres psql -U "$PGUSER" -d "$PGDB" -Atc "
SELECT 'wf='||w.id||' status='||w.status||' jobs='||count(j.id)||' done='||count(*) FILTER (WHERE j.status='COMPLETED')||' run='||count(*) FILTER (WHERE j.status='RUNNING')
FROM wf.workflows w JOIN wf.jobs j ON j.workflow_id=w.id
WHERE w.origin->>'test'='case26' AND w.created_at >= TIMESTAMPTZ '__FIRE__'
GROUP BY w.id, w.status
ORDER BY w.created_at DESC LIMIT 3;
" 2>/dev/null || true
  logs=$(hermes_logs | grep -E '\[zalo\] workflow job done|send-attachment path|workflow job failed|skip autosend' | tail -20)
  echo "LOGS_N=$(printf '%s\n' "$logs" | grep -c . || true)"
  printf '%s\n' "$logs" | tail -8
  done_n=$(hermes_logs | grep -c '\[zalo\] workflow job done' || true)
  attach_n=$(hermes_logs | grep -c 'send-attachment path' || true)
  echo "done_jobs=$done_n attach=$attach_n"
  if [ "${done_n:-0}" -ge 1 ] && [ "${attach_n:-0}" -ge 1 ]; then
    echo "JOB_DONE"
    echo "MEDIA_SENT"
    break
  fi
  sleep 12
done
echo "WATCH_END $(date -Is) done_jobs=$done_n attach=$attach_n"
echo WATCH_DONE
"""
        watch_sh = watch_sh.replace("__WAIT__", str(WAIT_S)).replace(
            "__SINCE__", since_iso
        ).replace("__FIRE__", fire_pg)
        watch = sudo_bash(c, watch_sh, timeout=WAIT_S + 90)
        print(_sanitize(watch[-3000:]), flush=True)
        (OUT / "watch.txt").write_text(_sanitize(watch), encoding="utf-8")
        job_ok = "JOB_DONE" in watch or "done_jobs=1" in watch
        media = "MEDIA_SENT" in watch
        if not media:
            for line in reversed(watch.splitlines()):
                if "attach=" in line:
                    raw = line.rsplit("attach=", 1)[-1].split()[0]
                    try:
                        media = int(raw) >= 1
                    except ValueError:
                        media = False
                    break
        if job_ok and not media:
            print("FAIL media created but not sent (attach=0)", flush=True)
        ok = job_ok and media
        (OUT / "SUMMARY.md").write_text(
            "\n".join(
                [
                    "# Case 26 Zalo weather+fuel infographic",
                    "",
                    f"- Time: `{ts()}`",
                    f"- Job done: **{'yes' if job_ok else 'no'}**",
                    f"- Media sent: **{'yes' if media else 'no'}**",
                    "",
                    "See `watch.txt`.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if RUN_DAILY:
            print("NOTE ZALO_INFOGRAPHIC_DAILY=1: classify daily is in this lab; full fire is case 27 optional", flush=True)
        daily_ok = "CLASSIFY_DAILY HINT schedule" in apply and "PLAN_N 1" in apply
        if "BAD_DAILY_PLAN" in apply:
            print("FAIL case27 daily classify", flush=True)
            daily_ok = False
        print(f"CASE27_CLASSIFY {'PASS' if daily_ok else 'FAIL'}", flush=True)
        return 0 if ok else 1
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

