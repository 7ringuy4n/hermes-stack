# -*- coding: utf-8 -*-
"""File/vision/YARA/AV matrix lab (SSH, separate from other labs).

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Reports: test/reports/run-file-pipeline-security/ (no host/account)
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import LOCAL_MODE, connect, sudo_bash
from sanitize import sanitize

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HOST = os.environ.get("ASSISTANT_SSH_HOST", "")
USER = os.environ.get("ASSISTANT_SSH_USER", "")
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-file-pipeline-security"
ROWS: list[dict] = []

EICAR = r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def note(name: str, status: str, detail: str = "") -> None:
    row = {"ts": ts(), "name": name, "status": status, "detail": sanitize(detail)[:800]}
    ROWS.append(row)
    print(f"[{row['ts']}] {name} | {status} | {row['detail'][:240]}", flush=True)


def main() -> int:
    if not LOCAL_MODE and (not HOST or not USER):
        print("SKIP: set ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    script = r'''
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
SM_PORT="${SECURITY_PORT:-8093}"
AV_PORT="${AV_GATEWAY_PORT:-8098}"
ROUTER_WORKER_PORT="${ROUTER_WORKER_PORT:-8096}"
printf '%s' 'X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*' > /tmp/eicar.com
printf 'hello clean lab19\n' > /tmp/clean.txt

probe_file() {
  name="$1"; url="$2"; f="$3"
  code=$(curl -sS -m 90 -o /tmp/fps-$name.json -w "%{http_code}" \
    -X POST "$url" -F "session_id=lab19-$name" -F "file=@$f" || echo 000)
  body=$(head -c 400 /tmp/fps-$name.json 2>/dev/null || true)
  echo "PROBE $name code=$code body=$body"
}

if curl -sf -m 5 "http://127.0.0.1:${SM_PORT}/health" >/dev/null 2>&1; then
  probe_file sm-clean "http://127.0.0.1:${SM_PORT}/v1/scan" /tmp/clean.txt
  probe_file sm-eicar "http://127.0.0.1:${SM_PORT}/v1/scan" /tmp/eicar.com
else
  echo "PROBE sm-clean code=SKIP body=security-manager not running"
  echo "PROBE sm-eicar code=SKIP body=security-manager not running"
fi

if curl -sf -m 5 "http://127.0.0.1:${AV_PORT}/health" >/dev/null 2>&1; then
  probe_file av-eicar "http://127.0.0.1:${AV_PORT}/v1/scan" /tmp/eicar.com
  for i in $(seq 1 24); do
    ready=$(curl -sS -m 8 "http://127.0.0.1:${AV_PORT}/v1/sessions/lab19-av-eicar/ready" || true)
    echo "AV_READY i=$i body=$ready"
    echo "$ready" | grep -qiE 'infected|blocked|ready.:true|"infected":1' && break
    sleep 2
  done
else
  echo "PROBE av-eicar code=SKIP body=av-gateway not running"
fi

if grep -qE '^SECURITY_URL=.+' /opt/assistant/.env /data/assistant/.env 2>/dev/null; then
  echo "INGEST_SECURITY_URL=set"
else
  echo "INGEST_SECURITY_URL=unset"
fi

if curl -sf -m 5 "http://127.0.0.1:${ROUTER_WORKER_PORT}/health" >/dev/null 2>&1; then
  echo "VISION_ROUTE_HEALTH=up"
else
  echo "VISION_ROUTE_HEALTH=down"
fi
'''
    try:
        out = sudo_bash(c, script)
    finally:
        c.close()
    fails = 0
    for line in out.splitlines():
        if not line.startswith("PROBE "):
            continue
        note("probe", "RECORD", line)
        low = line.lower()
        if "sm-eicar" in line and '"verdict":"CLEAN"' in line:
            note("sm-eicar", "FAIL", "EICAR not blocked at security-manager")
            fails += 1
        if "av-eicar" in line and "code=SKIP" not in line:
            if '"infected":1' in low or "blocked" in low:
                note("av-eicar", "RECORD", "infected/blocked in scan POST")
            elif '"status":"scanning"' in low:
                note("av-eicar", "RECORD", "async scan accepted")
    av_ready = "\n".join(l for l in out.splitlines() if l.startswith("AV_READY"))
    if av_ready:
        low_ready = av_ready.lower()
        if '"infected":1' in low_ready or "blocked" in low_ready or "infected" in low_ready:
            note("av-ready", "PASS", "EICAR infected/blocked after wait")
        elif "PROBE av-eicar code=SKIP" not in out:
            note("av-ready", "FAIL", "EICAR not infected after wait")
            fails += 1

    path = OUT / f"matrix-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps({"rows": ROWS, "fails": fails}, indent=2), encoding="utf-8")
    print(f"report={path.relative_to(ROOT)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
