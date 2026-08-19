# -*- coding: utf-8 -*-
"""Rolling VPS deploy: backup+verify, sync source, rebuild workflow + gateway + zalo-api, restart Hermes.

Does not destroy the stack. Does not run login-zalo / QR.
Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Reports: test/reports/run-feature-deploy/ (no host/account/secrets)
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_high import connect, sudo_bash, sync_tree  # noqa: E402
from sanitize import sanitize as _sanitize  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-feature-deploy"
ROWS: list[dict] = []


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def note(name: str, status: str, detail: str = "") -> None:
    row = {"ts": ts(), "name": name, "status": status, "detail": _sanitize(detail)[:800]}
    ROWS.append(row)
    print(f"[{row['ts']}] {name} | {status} | {row['detail'][:240]}", flush=True)


def write_report() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rows.json").write_text(json.dumps(ROWS, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Feature rolling deploy", "", f"- Timestamp: `{ts()}`", "", "| Step | Status | Detail |", "|------|--------|--------|"]
    for r in ROWS:
        lines.append(f"| {r['name']} | {r['status']} | {r['detail'][:160]} |")
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        probe = sudo_bash(
            c,
            r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
echo "PROFILE=${ASSISTANT_PROFILE:-unset}"
echo "REPLICAS=${HERMES_REPLICAS:-unset}"
echo "ZALO=${ENABLE_ZALO:-0}"
echo "AV=${ENABLE_ANTIVIRUS:-0}"
echo "TRAEFIK=${ENABLE_TRAEFIK:-0}"
echo "GATEWAY=${ENABLE_API_GATEWAY:-0}"
echo "=== PS ==="
docker ps --format '{{.Names}} {{.Status}}' | sort
echo "=== HEALTH ==="
curl -sS -m 8 -o /dev/null -w '9router_models:%{http_code}\n' http://127.0.0.1:20128/v1/models || echo 9ROUTER_DOWN
echo
curl -sS -m 8 http://127.0.0.1:8080/health || echo TRAEFIK_DOWN
echo
curl -sS -m 8 http://127.0.0.1:8090/health || echo DISPATCHER_DOWN
echo
echo PROBE_DONE
""",
            timeout=90,
        )
        note("probe", "pass" if "PROBE_DONE" in probe else "fail", probe[-400:])
        if "PROFILE=" in probe:
            for line in probe.splitlines():
                if line.startswith("PROFILE=") or line.startswith("ZALO=") or line.startswith("REPLICAS="):
                    note("probe_flag", "record", line)

        skip_backup = os.environ.get("SKIP_BACKUP", "0").strip() in {"1", "true", "yes"}
        verify_stamp = os.environ.get("VERIFY_STAMP", "").strip()
        if skip_backup:
            note("backup", "skip", f"SKIP_BACKUP=1 verify={verify_stamp or 'latest'}")
            bak = sudo_bash(
                c,
                rf"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
stamp="{verify_stamp}"
if [[ -z "$stamp" ]]; then
  stamp=$(ls -1 /data/assistant/backups 2>/dev/null | grep -E '^[0-9]{{8}}[_T][0-9]{{6}}' | tail -1 || true)
fi
echo "STAMP=${{stamp}}"
bash run.sh verify "$stamp"
echo BACKUP_VERIFY_OK
""",
                timeout=300,
            )
        else:
            note("backup", "start", "bash run.sh backup then verify")
            bak = sudo_bash(
                c,
                r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
out=$(bash run.sh backup)
echo "$out"
stamp=$(echo "$out" | grep -oE '[0-9]{8}[_T][0-9]{6}Z?' | tail -1 || true)
if [[ -z "$stamp" ]]; then
  stamp=$(ls -1 /data/assistant/backups 2>/dev/null | grep -E '^[0-9]{8}[_T][0-9]{6}' | tail -1 || true)
fi
echo "STAMP=${stamp}"
if [[ -z "$stamp" ]]; then
  echo "ERROR: no backup stamp"
  exit 1
fi
bash run.sh verify "$stamp"
echo BACKUP_VERIFY_OK
""",
                timeout=900,
            )
        if "BACKUP_VERIFY_OK" not in bak:
            note("backup", "fail", "verify did not succeed — abort deploy")
            write_report()
            return 1
        note("backup", "pass", "BACKUP_VERIFY_OK")

        note("sync", "start", "pack + extract source")
        sync_tree(c)
        note("sync", "pass", "SYNC_OK")

        note("apply", "start", "rebuild workflow + gateway + zalo-api, install stack-watch, restart hermes")
        apply = sudo_bash(
            c,
            r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
export COMPOSE_PROGRESS=plain
chmod +x /opt/assistant/scripts/main/stack-watch.sh || true
sed -i 's/\r$//' /opt/assistant/scripts/main/stack-watch.sh /opt/assistant/run.sh || true

# Keep edge/hostports: use run.sh compose via targeted recreate
files="-f /opt/assistant/docker/docker-compose.yml"
[[ "${ASSISTANT_PROFILE}" == "medium" || "${ASSISTANT_PROFILE}" == "high" ]] && files="$files -f /opt/assistant/docker/docker-compose.medium.yml"
[[ "${ASSISTANT_PROFILE}" == "high" ]] && files="$files -f /opt/assistant/docker/docker-compose.high.yml"
[[ "${ENABLE_TRAEFIK:-0}" == "1" || "${ENABLE_API_GATEWAY:-0}" == "1" ]] && files="$files -f /opt/assistant/docker/docker-compose.edge.yml"
[[ "${HERMES_REPLICAS:-1}" == "1" ]] && files="$files -f /opt/assistant/docker/docker-compose.hermes-hostports.yml"

profiles=""
[[ "${ENABLE_ZALO:-0}" == "1" ]] && profiles="$profiles --profile zalo"
[[ "${ENABLE_ANTIVIRUS:-0}" == "1" ]] && profiles="$profiles --profile antivirus"
[[ "${ENABLE_NOTIFY:-0}" == "1" ]] && profiles="$profiles --profile notify"
[[ "${ENABLE_OMNIROUTER:-0}" == "1" ]] && profiles="$profiles --profile omnirouter"
[[ "${ENABLE_TRAEFIK:-0}" == "1" ]] && profiles="$profiles --profile traefik"
[[ "${ENABLE_API_GATEWAY:-0}" == "1" ]] && profiles="$profiles --profile gateway"
[[ "${ENABLE_GRAFANA:-0}" == "1" ]] && profiles="$profiles --profile grafana"
[[ "${ENABLE_PROMETHEUS:-0}" == "1" ]] && profiles="$profiles --profile prometheus"
[[ "${ENABLE_LOKI:-0}" == "1" ]] && profiles="$profiles --profile loki"
[[ "${ENABLE_ALLOY:-0}" == "1" ]] && profiles="$profiles --profile alloy"

docker compose --project-directory /opt/assistant $files $profiles build workflow model-router
docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate workflow
docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate model-router
wf_ok=0
for _ in $(seq 1 30); do
  if curl -fsS -m 3 http://127.0.0.1:8108/health >/dev/null 2>&1; then
    wf_ok=1
    break
  fi
  sleep 2
done
echo "workflow_health=$wf_ok"
test "$wf_ok" = "1"
mr_ok=0
for _ in $(seq 1 30); do
  if curl -fsS -m 3 http://127.0.0.1:8096/health >/dev/null 2>&1; then
    mr_ok=1
    break
  fi
  sleep 2
done
echo "model_router_health=$mr_ok"
test "$mr_ok" = "1"
python3 /opt/assistant/test/scripts/migrate_jobs_to_workflow.py || true
echo SKIP_WORKFLOW_VPS

if [[ "${ENABLE_API_GATEWAY:-0}" == "1" ]]; then
  docker compose --project-directory /opt/assistant $files $profiles build api-gateway
  docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate api-gateway
fi

if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
  docker compose --project-directory /opt/assistant $files $profiles build zalo-api
  docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate zalo-api
fi
if [[ "${ENABLE_NOTIFY:-0}" == "1" ]]; then
  docker compose --project-directory /opt/assistant $files $profiles build notify
  docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate notify
fi

# Empty IMAGE_BACKENDS= in .env disables dispatcher image gen (Low). High must keep backends.
python3 - <<'PY'
from pathlib import Path
p = Path("/opt/assistant/.env")
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
want = "IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu"
out, seen, changed = [], False, False
for line in lines:
    if line.startswith("IMAGE_BACKENDS="):
        cur = line.split("=", 1)[1].strip().strip('"').strip("'")
        seen = True
        if not cur:
            out.append(want)
            changed = True
            print("IMAGE_BACKENDS_WAS_EMPTY")
        else:
            out.append(line)
            print(f"IMAGE_BACKENDS_KEEP={cur}")
    else:
        out.append(line)
if not seen:
    out.append(want)
    changed = True
    print("IMAGE_BACKENDS_ADDED")
if changed:
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("IMAGE_BACKENDS_WRITTEN")
PY
set -a; . ./.env; set +a
docker compose --project-directory /opt/assistant $files $profiles build session
docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate session
sleep 2
curl -sS -m 20 -X POST http://127.0.0.1:8107/v1/sessions/reset-all || echo SESSION_RESET_SKIP
echo SESSION_RESET_DONE
docker compose --project-directory /opt/assistant $files $profiles build dispatcher
docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate dispatcher
sleep 4
curl -sS -m 8 http://127.0.0.1:8090/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('image_backends', d.get('image_backends'))"
curl -sS -m 45 -X POST http://127.0.0.1:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"fill in 1 line \"IMGTEST\"","filename":"imgtest-poster.png","refine":false}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('poster', {k:d.get(k) for k in ('ok','backend','error','detail','file')})"

# Cron file must be group-readable: zalo-api wrote 0600 as root; Hermes could not tick lịch.
chown 1000:1000 /data/assistant/cron /data/assistant/cron/jobs.json 2>/dev/null || true
chmod 775 /data/assistant/cron 2>/dev/null || true
chmod 664 /data/assistant/cron/jobs.json 2>/dev/null || true
find /data/assistant/replicas -name jobs.json -exec chmod 664 {} + 2>/dev/null || true

# Overlay repo messages (protocol drop list) onto the shared mount.
if [[ -d /opt/assistant/hermes/main/messages ]]; then
  mkdir -p /data/assistant/messages
  cp -a /opt/assistant/hermes/main/messages/. /data/assistant/messages/ 2>/dev/null || true
fi
# Hermes Agent transcripts live under replica HERMES_HOME (not only Valkey).
# A huge sessions.json makes a 1-word ping compact + 413 on the LLM hop.
find /data/assistant/replicas -name sessions.json -not -path '*/home/.cache/*' -print -delete 2>/dev/null || true
# Hermes chat must go through model-router (compose default). Direct 9router inherits
# a huge context and returns 413 from the upstream model.
python3 - <<'PY'
from pathlib import Path
import re
p = Path("/opt/assistant/.env")
t = p.read_text(encoding="utf-8", errors="replace")
t2, n = re.subn(
    r"(?m)^HERMES_OPENAI_BASE_URL=.*9router.*$",
    "HERMES_OPENAI_BASE_URL=http://model-router:8096/v1",
    t,
)
if n:
    p.write_text(t2, encoding="utf-8")
    print("HERMES_OPENAI_TO_MODEL_ROUTER")
else:
    print("HERMES_OPENAI_UNCHANGED")
cfg = Path("/data/assistant/config.yaml")
if cfg.is_file():
    raw = cfg.read_text(encoding="utf-8", errors="replace")
    fixed = raw.replace("http://9router:20128/v1", "http://model-router:8096/v1")
    if fixed != raw:
        cfg.write_text(fixed, encoding="utf-8")
        print("HERMES_CONFIG_YAML_TO_MODEL_ROUTER")
    else:
        print("HERMES_CONFIG_YAML_UNCHANGED")
PY
set -a; . ./.env; set +a
# Overlay repo skills onto replica copies before restart (entrypoint used to cp -n and skip updates).
if [[ -d /opt/assistant/hermes/main/skills ]]; then
  for d in /data/assistant/replicas/*/skills; do
    [[ -d "$d" ]] || continue
    cp -a /opt/assistant/hermes/main/skills/. "$d"/
  done
fi
if [[ -d /opt/assistant/hermes/main/plugins ]]; then
  mkdir -p /data/assistant/plugins
  cp -a /opt/assistant/hermes/main/plugins/. /data/assistant/plugins/ 2>/dev/null || true
  for d in /data/assistant/replicas/*/plugins; do
    [[ -d "$d" ]] || continue
    cp -a /opt/assistant/hermes/main/plugins/. "$d"/
  done
  while IFS= read -r ad; do
    [[ -n "$ad" ]] || continue
    dir=$(dirname "$ad")
    cp -a /opt/assistant/hermes/main/plugins/zalo/*.py "$dir"/ 2>/dev/null || true
  done < <(find /data/assistant /opt/data -name adapter.py 2>/dev/null | grep -Ei 'zalo|zalo_platform' || true)
fi

# Hermes Zalo owner probes the host bridge at boot. Wait until it is logged in
# so adapter creation does not fail while inject-event is being patched.
for _ in $(seq 1 30); do
  if curl -fsS -m 5 http://127.0.0.1:8787/health | grep -q '"loggedIn":true'; then
    echo BRIDGE_READY_BEFORE_HERMES
    break
  fi
  sleep 2
done

# Recreate replicas so OPENAI_BASE_URL and overlaid plugins/messages take effect.
docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate --scale hermes="${HERMES_REPLICAS:-1}" hermes
hname=""
for _ in $(seq 1 24); do
  sleep 5
  hname=$(docker ps --filter name=hermes --filter status=running --format '{{.Names}}' | sort | head -1 || true)
  if [[ -n "$hname" ]] && docker exec "$hname" python3 -c "import urllib.request; urllib.request.urlopen('http://workflow:8108/health', timeout=5)" >/dev/null 2>&1; then
    break
  fi
done
echo "hermes_probe_container=${hname:-none}"

# Patch the host Node bridge after Hermes recreate. Restart only when newly patched
# so an existing inject-event route is not dropped (8787 Connection refused).
python3 /opt/assistant/scripts/main/patch_zalo_bridge_inject.py || echo INJECT_PATCH_FAIL
for _ in $(seq 1 20); do
  code=$(curl -sS -m 3 -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8787/inject-event -H 'Content-Type: application/json' -d '{}' || echo 000)
  echo "inject_http=$code"
  case "$code" in
    200|400|401|403) echo INJECT_ROUTE_OK; break ;;
  esac
  sleep 1
done
for _ in $(seq 1 30); do
  if curl -fsS -m 5 http://127.0.0.1:8787/health | grep -q '"loggedIn":true'; then
    echo BRIDGE_LOGGED_IN
    break
  fi
  sleep 2
done

echo "=== POST HEALTH ==="
ok=1
n9c=$(curl -sS -m 8 -o /dev/null -w '%{http_code}' http://127.0.0.1:20128/ || echo 000)
# 9router UI: / is 307, /health is 404, /v1/models is 401 — any of these means the process is up
case "$n9c" in
  200|307|401|404) echo "9router_http=$n9c" ;;
  *) echo 9ROUTER_DOWN; ok=0 ;;
esac
curl -fsS -m 8 http://127.0.0.1:8090/health >/dev/null || { echo DISPATCHER_DOWN; ok=0; }
tr_ok=0
for _ in $(seq 1 12); do
  if curl -fsS -m 8 http://127.0.0.1:8080/health >/dev/null 2>&1; then
    tr_ok=1
    break
  fi
  sleep 2
done
if [[ "$tr_ok" != "1" ]]; then
  echo TRAEFIK_DOWN
  ok=0
fi
curl -fsS -m 8 http://127.0.0.1:8108/health >/dev/null || { echo WORKFLOW_DOWN; ok=0; }
if [[ "${ENABLE_API_GATEWAY:-0}" == "1" ]]; then
  curl -fsS -m 8 http://127.0.0.1:8088/health >/dev/null || { echo GATEWAY_DOWN; ok=0; }
fi
if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
  curl -fsS -m 8 http://127.0.0.1:8100/health >/dev/null || { echo ZALO_API_DOWN; ok=0; }
fi
echo -n "hermes_to_9router="
if [[ -n "$hname" ]]; then
  docker exec "$hname" python3 -c "import urllib.request; urllib.request.urlopen('http://9router:20128/', timeout=5); print('ok')" 2>/dev/null || { echo fail; ok=0; }
else
  echo fail; ok=0
fi
echo -n "hermes_to_model_router="
if [[ -n "$hname" ]]; then
  docker exec "$hname" python3 -c "import urllib.request; urllib.request.urlopen('http://model-router:8096/health', timeout=5); print('ok')" 2>/dev/null || { echo fail; ok=0; }
else
  echo fail; ok=0
fi
echo -n "hermes_to_workflow="
if [[ -n "$hname" ]]; then
  docker exec "$hname" python3 -c "import urllib.request; urllib.request.urlopen('http://workflow:8108/health', timeout=5); print('ok')" 2>/dev/null || { echo fail; ok=0; }
else
  echo fail; ok=0
fi
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
docker ps --filter name=workflow --format '{{.Names}} {{.Status}}'
test -f /opt/assistant/hermes/main/plugins/zalo/multi_request.py && echo files_multi=ok || echo files_multi=missing
test -f /opt/assistant/hermes/main/plugins/zalo/inbound_queue.py && echo files_queue=ok || echo files_queue=missing
test -f /opt/assistant/hermes/main/plugins/zalo/autosend.py && echo files_autosend=ok || echo files_autosend=missing
test -f /opt/assistant/hermes/main/plugins/zalo/workflow_client.py && echo files_workflow=ok || echo files_workflow=missing
test -f /opt/assistant/hermes/main/plugins/zalo/turn_wait.py && echo files_turn_wait=ok || echo files_turn_wait=missing
test -f /opt/assistant/hermes/main/plugins/zalo/knowledge_cite.py && echo files_knowledge_cite=ok || { echo files_knowledge_cite=missing; ok=0; }
if grep -q 'not a knowledge-base lookup' /opt/assistant/architect/models/model-router/config/classify.json && grep -q 'task_hint=knowledge' /opt/assistant/architect/models/model-router/config/classify.json; then
  echo files_classify_nocite=ok
else
  echo files_classify_nocite=missing
  ok=0
fi
if grep -q 'execution_class' /opt/assistant/architect/models/model-router/config/classify.json; then
  echo files_fast_dispatcher=ok
else
  echo files_fast_dispatcher=missing
  ok=0
fi
test -f /opt/assistant/hermes/main/plugins/zalo/classify_client.py && echo files_classify_client=ok || { echo files_classify_client=missing; ok=0; }
test -f /opt/assistant/hermes/main/plugins/zalo/gateway_noise.py && echo files_gateway_noise=ok || { echo files_gateway_noise=missing; ok=0; }
if [[ -n "$hname" ]] && docker exec "$hname" python3 -c "import sys; sys.path.insert(0,'/opt/data/plugins/zalo'); import classify_client, gateway_noise; print('replica_plugin_import=ok')" 2>/dev/null; then
  :
else
  echo replica_plugin_import=fail
  ok=0
fi
test -f /opt/assistant/hermes/main/skills/image-gen/SKILL.md && echo files_image_gen=ok || echo files_image_gen=missing
if grep -q 'Never' /opt/assistant/hermes/main/skills/image-gen/SKILL.md && grep -q 'web_extract' /opt/assistant/hermes/main/skills/image-gen/SKILL.md; then
  echo files_image_gen_noscrape=ok
else
  echo files_image_gen_noscrape=missing
  ok=0
fi
rep_ok=0
for f in /data/assistant/replicas/*/skills/image-gen/SKILL.md; do
  [[ -f "$f" ]] || continue
  if grep -q 'web_extract' "$f" && grep -q 'Never' "$f"; then
    rep_ok=1
  fi
done
if [[ "$rep_ok" = "1" ]]; then
  echo replica_image_gen_noscrape=ok
else
  echo replica_image_gen_noscrape=missing
  ok=0
fi
if grep -q 'session' /opt/assistant/hermes/main/messages/ux.json && grep -q 'interrupted' /opt/assistant/hermes/main/messages/ux.json; then
  echo files_ux_session=ok
else
  echo files_ux_session=missing
  ok=0
fi
test -f /opt/assistant/architect/workflow/app.py && echo files_wf_svc=ok || echo files_wf_svc=missing
python3 - <<'PY'
from pathlib import Path
p = Path("/data/assistant/cron/jobs.json")
if p.is_file():
    st = p.stat()
    print(f"cron_mode={oct(st.st_mode & 0o777)} uid={st.st_uid} gid={st.st_gid}")
else:
    print("cron_mode=missing")
PY
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/data/assistant/cron/jobs.json")
if not p.is_file():
    raise SystemExit(0)
data = json.loads(p.read_text(encoding="utf-8"))
jobs = data.get("jobs") if isinstance(data.get("jobs"), list) else []
print(f"cron_n={len(jobs)}")
for j in jobs:
    if not isinstance(j, dict):
        continue
    expr = str(j.get("schedule") or j.get("cron") or j.get("expr") or "")
    prompt = str(j.get("prompt") or "")
    last = str(j.get("last_run") or j.get("lastRun") or "")[:32]
    no_agent = j.get("no_agent")
    print(f"expr={expr} prompt_len={len(prompt)} last={last or '-'} no_agent={no_agent}")
PY
echo "HERMES_9ROUTER_OK=$ok"
echo APPLY_DONE
""",
            timeout=900,
        )
        if "APPLY_DONE" not in apply:
            note("apply", "fail", "missing APPLY_DONE")
            write_report()
            return 1
        if "HERMES_9ROUTER_OK=1" in apply:
            note("hermes_9router", "pass", "9router health+models and edge probes ok")
        else:
            note("hermes_9router", "fail", apply[-500:])
        if "PASS workflow vps" in apply:
            note("workflow_vps", "pass", "health + 3-job drain + plan")
        if "PASS migrate" in apply:
            note("migrate_schedules", "pass", "jobs.json → workflow")
        if "WORKFLOW_DOWN" in apply:
            note("workflow_health", "fail", "8108 down after apply")
        note("apply", "pass", "APPLY_DONE")

        admin = sudo_bash(
            c,
            r"""
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
env = {}
for line in Path("/opt/assistant/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
print("ADMIN_BEGIN")
for k in [
    "ASSISTANT_PROFILE","HERMES_REPLICAS","ENABLE_ZALO","ENABLE_ANTIVIRUS",
    "HERMES_DASHBOARD_USER","HERMES_DASHBOARD_PASSWORD",
    "GRAFANA_ADMIN_USER","GRAFANA_ADMIN_PASSWORD",
]:
    print(f"{k}={env.get(k,'')}")
print("ADMIN_END")
PY
""",
            timeout=30,
        )
        if "ADMIN_BEGIN" in admin:
            start = admin.index("ADMIN_BEGIN")
            end = admin.index("ADMIN_END") + len("ADMIN_END")
            user = ""
            pw_set = False
            for line in admin[start:end].splitlines():
                if line.startswith("HERMES_DASHBOARD_USER="):
                    user = line.split("=", 1)[1]
                if line.startswith("HERMES_DASHBOARD_PASSWORD=") and line.split("=", 1)[1].strip():
                    pw_set = True
            note("admin", "pass", f"dashboard_user={user or '[set]'} password={'set' if pw_set else 'missing'}")

        write_report()
        fails = [r for r in ROWS if r["status"] == "fail"]
        return 1 if fails else 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
