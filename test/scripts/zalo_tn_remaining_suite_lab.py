#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remaining RULES Tn suite: image-gen rate, vision-ocr, docs OCR, web-search, schedule.

Uses samples from local ``../test docs`` (OCR + Security). Rates with Omni vision /
ingest extract (AGENT_RULES §29.2).

Env: ASSISTANT_SSH_*, optional ZALO_TEST_USER_ID, ZALO_SUITE_WAIT_S, ASSISTANT_TEST_DOCS
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash, sftp_put, _file_bytes  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
DOCS = Path(os.environ.get("ASSISTANT_TEST_DOCS") or (ROOT.parent / "test docs"))
OUT = ROOT / "test" / "reports" / "run-zalo-tn-remaining-suite"
REMOTE_PY = Path(__file__).resolve().parent / "zalo_tn_remaining_suite_remote.py"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
WAIT_S = int(os.environ.get("ZALO_SUITE_WAIT_S") or "360")

SAMPLES = [
    ("OCR/tired_man_test.png", "tired_man_test.png"),
    ("OCR/hcmc_weather_report.pdf", "hcmc_weather_report.pdf"),
    ("OCR/message.txt", "message.txt"),
    ("Security/img.png", "sec_img.png"),
]


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _clean(text: str) -> str:
    lines = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        if "sudo" in low and "password" in low:
            continue
        if low.startswith("[sudo"):
            continue
        lines.append(s)
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [a for a, _ in SAMPLES if not (DOCS / a).is_file()]
    if missing:
        print("FAIL missing local samples:", missing)
        return 2
    if not REMOTE_PY.is_file():
        print("FAIL missing", REMOTE_PY)
        return 2

    c = connect()
    print(
        sudo_bash(
            c,
            "mkdir -p /tmp/hs-suite /data/assistant/lab-samples && chmod 777 /tmp/hs-suite",
            timeout=30,
        )
    )
    for rel, name in SAMPLES:
        print("PUT", rel, flush=True)
        sftp_put(c, _file_bytes(DOCS / rel), f"/tmp/hs-suite/{name}")
    sftp_put(c, _file_bytes(REMOTE_PY), "/tmp/hs-suite/remaining_suite_remote.py")
    install_cmds = [
        "set -euo pipefail",
        "ls -la /tmp/hs-suite",
        "mkdir -p /data/assistant/lab-samples /opt/assistant/test/scripts",
    ]
    for _, name in SAMPLES:
        install_cmds.append(
            f"cp -f /tmp/hs-suite/{name} /data/assistant/lab-samples/{name}"
        )
    install_cmds.append(
        "cp -f /tmp/hs-suite/remaining_suite_remote.py /opt/assistant/test/scripts/zalo_tn_remaining_suite_remote.py"
    )
    print(_clean(sudo_bash(c, "\n".join(install_cmds), timeout=60)))

    remote = f"""
set -euo pipefail
export LC_ALL=C.UTF-8
export ZALO_TEST_USER_ID={TN_ID!r}
export ZALO_SUITE_WAIT_S={WAIT_S}
python3 /opt/assistant/test/scripts/zalo_tn_remaining_suite_remote.py
"""
    out = _clean(sudo_bash(c, remote, timeout=WAIT_S * 4 + 400))
    (OUT / "remote.txt").write_text(out, encoding="utf-8")
    print(out)
    verdict = "PASS" if "VERDICT PASS" in out else "FAIL"
    report = {"ts": ts(), "verdict": verdict}
    try:
        for ln in reversed(out.splitlines()):
            if ln.startswith("{") and '"checks"' in ln:
                report["payload"] = json.loads(ln)
                break
    except Exception:
        pass
    (OUT / "SUMMARY.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("REPORT", OUT / "SUMMARY.json", verdict)
    c.close()
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
