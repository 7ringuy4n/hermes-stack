# -*- coding: utf-8 -*-
"""Run schedule TZ or multi-request unit tests on the VPS (one case per process).

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
     CASE=15|16|22|23|24
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
CASE = os.environ.get("CASE", "").strip()


def main() -> int:
    if CASE not in {"15", "16", "22", "23", "24"}:
        print("FAIL: set CASE=15, 16, 22, 23, or 24")
        return 2
    c = connect()
    try:
        scripts = {
            "15": "/opt/assistant/test/scripts/schedule_timezone_unit.py",
            "16": "/opt/assistant/test/scripts/multi_request_unit.py",
            "22": "/opt/assistant/test/scripts/gateway_noise_unit.py",
            "23": "/opt/assistant/test/scripts/inbound_queue_unit.py",
            "24": "/opt/assistant/test/scripts/workflow_schedule_concurrency_unit.py",
        }
        script = scripts[CASE]
        out = sudo_bash(
            c,
            f"sed -i 's/\\r$//' {script}; python3 {script}",
            timeout=60,
        )
        print(out[-800:])
        return 0 if "PASS" in out and "FAIL" not in out else 1
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

