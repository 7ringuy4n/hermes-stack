# -*- coding: utf-8 -*-
"""Live Model Router and OmniRoute connectivity (SSH).

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Reports: test/reports/run-defaults-routers/ (no host/account)
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
OUT = ROOT / "test" / "reports" / "run-defaults-routers"
ROWS: list[dict] = []
SLO_MS = int(os.environ.get("SIMPLE_MSG_SLO_MS", "5000"))


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
            rf"""
set -euo pipefail
trap 'rm -f /tmp/def-ping.json' EXIT
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
echo "PROFILE=${{ASSISTANT_PROFILE:-unset}}"
echo "MODEL_ROUTER=${{ENABLE_MODEL_ROUTER:-1}}"
echo "OMNI=${{ENABLE_OMNIROUTER:-0}}"
echo "GRAFANA=${{ENABLE_GRAFANA:-0}}"
echo "mr=$(docker inspect -f '{{{{.State.Status}}}}' model-router 2>/dev/null || echo missing)"
echo "omni=$(docker inspect -f '{{{{.State.Status}}}}' omni-router 2>/dev/null || echo missing)"
echo -n "hermes_to_model_router="
docker exec assistant-hermes-1 python3 -c "import urllib.request; urllib.request.urlopen('http://model-router:8096/health', timeout=5); print('ok')" 2>/dev/null || echo fail
echo "mr_health=$(curl -sS -m 5 -o /dev/null -w '%{{http_code}}' http://127.0.0.1:8096/health || echo fail)"
echo "omni_root=$(curl -sS -m 5 -o /dev/null -w '%{{http_code}}' http://127.0.0.1:20129/ || echo fail)"
KEY="${{API_SERVER_KEY:-}}"
if [[ -n "$KEY" ]]; then
  t0=$(date +%s%3N)
  code=$(curl -sS -m 60 -o /tmp/def-ping.json -w "%{{http_code}}" \
    -X POST http://127.0.0.1:8080/v1/chat/completions \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d '{{"model":"hermes","messages":[{{"role":"user","content":"ping reply OK"}}],"max_tokens":8}}' || echo 000)
  t1=$(date +%s%3N)
  echo "PING_HTTP=$code PING_MS=$((t1-t0))"
else
  echo "PING_HTTP=SKIP PING_MS=0"
fi
echo DEFAULTS_LAB_DONE
""",
            timeout=90,
        )
        fails = 0
        if "DEFAULTS_LAB_DONE" not in out:
            note("lab", "FAIL", "missing done marker")
            return 1
        if "MODEL_ROUTER=0" in out:
            note("model_router", "RECORD", "flag off (non-default)")
        elif "hermes_to_model_router=ok" not in out:
            note("model_router", "FAIL", "Hermes cannot reach model-router")
            fails += 1
        else:
            note("model_router", "PASS", "connected")
        omni_flag_on = "OMNI=1" in out or "OMNI=active" in out
        omni_running = "omni=running" in out
        if omni_flag_on != omni_running:
            note("omni_match", "FAIL", "flag vs container mismatch")
            fails += 1
        else:
            note("omni_match", "PASS", "flag matches container")
        if not omni_flag_on:
            note("omni_default", "FAIL", "live OmniRoute is disabled")
            fails += 1
        else:
            note("omni_default", "PASS", "live OmniRoute enabled")
        for line in out.splitlines():
            if line.startswith("PING_HTTP="):
                note("ping", "RECORD", line)
                parts = line.replace("PING_HTTP=", "").replace("PING_MS=", "").split()
                if len(parts) >= 2 and parts[0] == "200" and parts[1].isdigit():
                    ms = int(parts[1])
                    if ms > SLO_MS:
                        note("ping_slo", "FAIL", f"{ms}ms > {SLO_MS}ms simple-message SLO")
                        fails += 1
                    else:
                        note("ping_slo", "PASS", f"{ms}ms")
        path = OUT / f"defaults-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
        path.write_text(json.dumps({"rows": ROWS, "fails": fails}, indent=2), encoding="utf-8")
        print(f"report={path.relative_to(ROOT)}")
        return 1 if fails else 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

