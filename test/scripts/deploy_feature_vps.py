# -*- coding: utf-8 -*-
"""Rolling VPS deploy: backup+verify, sync source, rebuild zalo-api, restart Hermes.

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

        note("apply", "start", "rebuild zalo-api, install stack-watch, restart hermes")
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

if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
  docker compose --project-directory /opt/assistant $files $profiles build zalo-api
  docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate zalo-api
fi

# Bind-mounted skills/plugins/SOUL — restart replicas to pick up files
docker ps -q --filter name=hermes --filter status=running | xargs -r docker restart
sleep 12

echo "=== POST HEALTH ==="
ok=1
n9c=$(curl -sS -m 8 -o /dev/null -w '%{http_code}' http://127.0.0.1:20128/ || echo 000)
# 9router UI: / is 307, /health is 404, /v1/models is 401 — any of these means the process is up
case "$n9c" in
  200|307|401|404) echo "9router_http=$n9c" ;;
  *) echo 9ROUTER_DOWN; ok=0 ;;
esac
curl -fsS -m 8 http://127.0.0.1:8090/health >/dev/null || { echo DISPATCHER_DOWN; ok=0; }
curl -fsS -m 8 http://127.0.0.1:8080/health >/dev/null || { echo TRAEFIK_DOWN; ok=0; }
if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
  curl -fsS -m 8 http://127.0.0.1:8100/health >/dev/null || { echo ZALO_API_DOWN; ok=0; }
fi
echo -n "hermes_to_9router="
docker exec assistant-hermes-1 python3 -c "import urllib.request; urllib.request.urlopen('http://9router:20128/', timeout=5); print('ok')" 2>/dev/null || { echo fail; ok=0; }
echo -n "hermes_to_model_router="
docker exec assistant-hermes-1 python3 -c "import urllib.request; urllib.request.urlopen('http://model-router:8096/health', timeout=5); print('ok')" 2>/dev/null || { echo fail; ok=0; }
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
test -f /opt/assistant/hermes/main/plugins/zalo/multi_request.py && echo files_multi=ok || echo files_multi=missing
test -f /opt/assistant/hermes/main/plugins/zalo/inbound_queue.py && echo files_queue=ok || echo files_queue=missing
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
            # Print to operator stdout only (not written to SUMMARY)
            print(admin[start:end], flush=True)
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
