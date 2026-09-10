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
from classify_fixtures import (  # noqa: E402
    FIXTURE_INFOGRAPHIC_DAILY,
    FIXTURE_INFOGRAPHIC_SPLIT_VI,
    FIXTURE_INFOGRAPHIC_VI,
)
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
        marker = f"case26-grounded-image-{int(time.time())}"
        print(f"[{ts()}] inject dependency workflow", flush=True)
        apply = sudo_bash(
            c,
            rf"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, os, urllib.request
from pathlib import Path

text = {FIXTURE_INFOGRAPHIC_SPLIT_VI!r}

def post(url, body, timeout=120):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={{"Content-Type":"application/json"}})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{{}}")

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
import subprocess
offsets=[]
names=subprocess.check_output(["docker","ps","--format","{{{{.Names}}}}"],text=True).splitlines()
for name in names:
    if not name.startswith("assistant-hermes-"):
        continue
    count=subprocess.check_output(
        ["docker","exec",name,"sh","-lc","wc -l < /opt/data/replicas/$(hostname)/logs/agent.log"],
        text=True,
    ).strip()
    offsets.append(name+" "+str(int(count or "0")+1))
Path("/tmp/case26-log-offsets").write_text("\n".join(offsets)+"\n",encoding="utf-8")
payload={{
    "type":"message","threadId":admin_id,"threadType":"user",
    "senderId":admin_id,"senderName":"test-user","text":text,
    "messageId":{marker!r},
}}
got = post("http://127.0.0.1:8787/inject-event", payload, 30)
print("INJECT", got.get("ok"), "MARKER", {marker!r})
if not got.get("ok"):
    raise SystemExit("BAD_INJECT")
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
        if "BAD_INJECT" in apply:
            print("FAIL channel injection", flush=True)
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
  while read -r n start; do
    [ -n "$n" ] || continue
    docker exec "$n" sh -lc "tail -n +$start /opt/data/replicas/\$(hostname)/logs/agent.log" 2>/dev/null
  done < /tmp/case26-log-offsets
}
done_n=0
attach_n=0
delivered_n=0
evidence_n=0
planner_invalid_n=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  curl -sS -m 5 http://127.0.0.1:8787/health 2>/dev/null | python3 -c 'import sys,json
try:
 d=json.load(sys.stdin); print("plugin loggedIn", d.get("loggedIn"), "sse", d.get("sseClients"))
except Exception:
 print("plugin raw")
' || echo "plugin down"
  history=$(docker exec -e PGPASSWORD="$PGPASSWORD" postgres psql -U "$PGUSER" -d "$PGDB" -Atc "
SELECT event||' source='||coalesce(meta->>'source_message_id','')||' attachment='||coalesce(meta->>'attachment_kind','')
FROM zalo_message_history
WHERE message_id='__MARKER__' OR meta->>'source_message_id'='__MARKER__'
ORDER BY id;
" 2>/dev/null || true)
  printf '%s\n' "$history"
  logs=$(hermes_logs | grep -E 'composed image evidence plan|image structured planning invalid|search_composed_image_shortcut|send-attachment path|send-attachment fail' | tail -20)
  echo "LOGS_N=$(printf '%s\n' "$logs" | grep -c . || true)"
  printf '%s\n' "$logs" | tail -8
  done_n=$(hermes_logs | grep -c 'search_composed_image_shortcut' || true)
  attach_n=$(hermes_logs | grep -c 'send-attachment path' || true)
  delivered_n=$(printf '%s\n' "$history" | grep -c 'delivered source=__MARKER__ attachment=image' || true)
  evidence_n=$(hermes_logs | grep -Ec 'composed image evidence plan queries=[2-4]' || true)
  planner_invalid_n=$(hermes_logs | grep -c 'image structured planning invalid' || true)
  echo "done_jobs=$done_n attach=$attach_n delivered=$delivered_n evidence=$evidence_n planner_invalid=$planner_invalid_n"
  if [ "${done_n:-0}" -ge 1 ] && [ "${attach_n:-0}" -ge 1 ] && [ "${delivered_n:-0}" -ge 1 ] && [ "${evidence_n:-0}" -ge 1 ] && [ "${planner_invalid_n:-0}" -eq 0 ]; then
    echo "JOB_DONE"
    echo "MEDIA_SENT"
    echo "DELIVERY_RECORDED"
    echo "EVIDENCE_DECOMPOSED"
    echo "PLANNER_JSON_COMPLETE"
    break
  fi
  sleep 12
done
echo "WATCH_END $(date -Is) done_jobs=$done_n attach=$attach_n delivered=$delivered_n evidence=$evidence_n planner_invalid=$planner_invalid_n"
echo WATCH_DONE
"""
        watch_sh = watch_sh.replace("__WAIT__", str(WAIT_S)).replace(
            "__SINCE__", since_iso
        ).replace("__FIRE__", fire_pg).replace("__MARKER__", marker)
        watch = sudo_bash(c, watch_sh, timeout=WAIT_S + 90)
        print(_sanitize(watch[-3000:]), flush=True)
        job_ok = "JOB_DONE" in watch or "done_jobs=1" in watch
        media = "MEDIA_SENT" in watch
        recorded = "DELIVERY_RECORDED" in watch
        evidence_decomposed = "EVIDENCE_DECOMPOSED" in watch
        planner_complete = "PLANNER_JSON_COMPLETE" in watch
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
        ok = job_ok and media and recorded and evidence_decomposed and planner_complete
        (OUT / "watch.txt").write_text(
            "\n".join(
                [
                    f"job_done={'yes' if job_ok else 'no'}",
                    f"media_sent={'yes' if media else 'no'}",
                    f"delivery_recorded={'yes' if recorded else 'no'}",
                    f"evidence_decomposed={'yes' if evidence_decomposed else 'no'}",
                    f"planner_json_complete={'yes' if planner_complete else 'no'}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        print(f"[{ts()}] verify classifier contracts after live delivery", flush=True)
        classify = sudo_bash(
            c,
            rf"""
set -euo pipefail
python3 - <<'PY'
import json, urllib.request

def classify(text):
    data = json.dumps({{"text": text, "timezone": "Asia/Ho_Chi_Minh"}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8096/v1/classify", data=data, method="POST", headers={{"Content-Type": "application/json"}})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode() or "{{}}")

def task_types(result):
    details = result.get("task_details") if isinstance(result.get("task_details"), list) else []
    return [str(item.get("task_type") or "") for item in details if isinstance(item, dict)]

now = classify({FIXTURE_INFOGRAPHIC_SPLIT_VI!r})
now_types = task_types(now)
details = now.get("task_details") if isinstance(now.get("task_details"), list) else []
search_indexes = [i for i, item in enumerate(details) if isinstance(item, dict) and str(item.get("task_type") or "") == "search"]
media = [item for item in details if isinstance(item, dict) and str(item.get("task_type") or "") == "media_generation"]
media_dependencies = media[0].get("depends_on") if len(media) == 1 and isinstance(media[0].get("depends_on"), list) else []
now_ok = bool(now.get("ok")) and str(now.get("task_hint") or "") != "schedule" and len(search_indexes) >= 1 and len(media) == 1 and all(index in media_dependencies for index in search_indexes)
print("NOW_CONTRACT", "PASS" if now_ok else "FAIL", "HINT", now.get("task_hint"), "TYPES", ",".join(now_types))

daily = classify({FIXTURE_INFOGRAPHIC_DAILY!r})
daily_types = task_types(daily)
daily_ok = bool(daily.get("ok")) and str(daily.get("task_hint") or "") == "schedule" and daily_types.count("search") >= 1 and daily_types.count("media_generation") == 1
print("DAILY_CONTRACT", "PASS" if daily_ok else "FAIL", "HINT", daily.get("task_hint"), "TYPES", ",".join(daily_types))
if not now_ok or not daily_ok:
    raise SystemExit(1)
PY
""",
            timeout=300,
        )
        print(_sanitize(classify[-1800:]), flush=True)
        now_ok = "NOW_CONTRACT PASS" in classify
        daily_ok = "DAILY_CONTRACT PASS" in classify
        ok = ok and now_ok and daily_ok
        (OUT / "SUMMARY.md").write_text(
            "\n".join(
                [
                    "# Case 26 Zalo weather+fuel infographic",
                    "",
                    f"- Time: `{ts()}`",
                    f"- Job done: **{'yes' if job_ok else 'no'}**",
                    f"- Media sent: **{'yes' if media else 'no'}**",
                    f"- Delivery recorded: **{'yes' if recorded else 'no'}**",
                    f"- Evidence decomposed: **{'yes' if evidence_decomposed else 'no'}**",
                    f"- Planner JSON complete: **{'yes' if planner_complete else 'no'}**",
                    f"- Immediate classifier contract: **{'yes' if now_ok else 'no'}**",
                    f"- Daily classifier contract: **{'yes' if daily_ok else 'no'}**",
                    "",
                    "See `watch.txt`.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if RUN_DAILY:
            print("NOTE ZALO_INFOGRAPHIC_DAILY=1: classify daily is in this lab; full fire is case 27 optional", flush=True)
        print(f"CASE27_CLASSIFY {'PASS' if daily_ok else 'FAIL'}", flush=True)
        return 0 if ok else 1
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

