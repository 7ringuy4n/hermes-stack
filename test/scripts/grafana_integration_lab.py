# -*- coding: utf-8 -*-
"""Grafana integration lab (SSH). Skip when ENABLE_GRAFANA=0.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Reports: test/reports/run-grafana-integration/ (no host/account)
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
from sanitize import sanitize

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-grafana-integration"
ROWS: list[dict] = []


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def note(name: str, status: str, detail: str = "") -> None:
    row = {"ts": ts(), "name": name, "status": status, "detail": sanitize(detail)[:800]}
    ROWS.append(row)
    print(f"[{row['ts']}] {name} | {status} | {row['detail'][:240]}", flush=True)


def main() -> int:
    if not os.environ.get("ASSISTANT_SSH_HOST"):
        print("SKIP: set ASSISTANT_SSH_* to run the lab")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
echo "GRAFANA=${ENABLE_GRAFANA:-0}"
echo "PROMETHEUS=${ENABLE_PROMETHEUS:-0}"
echo "OMNI=${ENABLE_OMNIROUTER:-0}"
echo "AV=${ENABLE_ANTIVIRUS:-0}"
echo "ZALO=${ENABLE_ZALO:-0}"
case "${ENABLE_GRAFANA:-0}:${ENABLE_PROMETHEUS:-0}" in
  active:*|1:*|*:active|*:1) ;;
  *)
  echo SKIP_GRAFANA_OFF
  exit 0
  ;;
esac
echo "grafana_health=$(curl -sS -m 8 -o /dev/null -w '%{http_code}' http://127.0.0.1:23000/api/health || echo fail)"
curl -sS -m 8 http://127.0.0.1:23000/api/health || true
echo
echo '=== PROM_TARGETS ==='
docker exec stack-exporter python -c '
import json, urllib.request
d=json.loads(urllib.request.urlopen("http://prometheus:9090/api/v1/targets", timeout=8).read().decode())
for t in (d.get("data") or {}).get("activeTargets") or []:
    job=(t.get("labels") or {}).get("job","")
    health=t.get("health","")
    err=(t.get("lastError") or "")[:60]
    print(f"TARGET job={job} health={health} err={err}")
'
echo '=== SERVICE_UP ==='
docker exec stack-exporter python -c '
import urllib.request
t=urllib.request.urlopen("http://127.0.0.1:9102/metrics", timeout=8).read().decode()
for line in t.splitlines():
    if line.startswith("assistant_service_up"):
        print(line)
'
if [[ "${ENABLE_OMNIROUTER:-0}" == "1" || "${ENABLE_OMNIROUTER:-0}" == "active" ]]; then
  echo '=== OMNI ==='
  docker exec omni-exporter python -c '
import urllib.request
t=urllib.request.urlopen("http://127.0.0.1:9104/metrics", timeout=8).read().decode()
for line in t.splitlines():
    if line.startswith("omnirouter_scrape_success"):
        print(line)
' 2>/dev/null || echo OMNI_EXPORTER_ABSENT
fi
echo GRAFANA_LAB_DONE
""",
            timeout=90,
        )
        if "SKIP_GRAFANA_OFF" in out:
            note("grafana", "SKIP", "ENABLE_GRAFANA/PROMETHEUS off")
            return 0
        fails = 0
        if "GRAFANA_LAB_DONE" not in out:
            note("lab", "FAIL", "missing GRAFANA_LAB_DONE")
            return 1
        if "grafana_health=200" not in out:
            note("grafana_ui", "FAIL", "Grafana /api/health not 200")
            fails += 1
        else:
            note("grafana_ui", "PASS", "health 200")
        down = [
            line
            for line in out.splitlines()
            if line.startswith("assistant_service_up") and line.rstrip().endswith(" 0")
        ]
        # Optionals that may be 0 when flags off
        ignore = ("av-gateway", "clamav", "notify", "alert-watch", "zalo-api")
        real_down = [d for d in down if not any(f'service="{n}"' in d or f'service=\\"{n}\\"' in d for n in ignore)]
        # simpler: skip known optional names
        real_down = []
        for d in down:
            if any(name in d for name in ("av-gateway", "clamav", "notify", "alert-watch")):
                continue
            if "zalo-api" in d and "ZALO=0" in out:
                continue
            if "omni-router" in d and "OMNI=0" in out:
                continue
            real_down.append(d)
        if real_down:
            note("service_up", "FAIL", "; ".join(real_down)[:400])
            fails += 1
        else:
            note("service_up", "PASS", "expected services up")
        if "OMNI=1" in out and "omnirouter_scrape_success" in out:
            if "omnirouter_scrape_success 0" in out:
                note("omni", "FAIL", "omni scrape 0")
                fails += 1
            else:
                note("omni", "PASS", "omni scrape")
        path = OUT / f"grafana-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
        path.write_text(json.dumps({"rows": ROWS, "fails": fails}, indent=2), encoding="utf-8")
        print(f"report={path.relative_to(ROOT)}")
        return 1 if fails else 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

