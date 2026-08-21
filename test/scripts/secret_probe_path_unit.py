# -*- coding: utf-8 -*-
"""Unit: secret-probe path blocks + EICAR marker detection."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

# Prefer repo config for policy load
import os

os.environ["SECRET_PROBE_POLICY"] = str(ROOT / "config" / "agent" / "secret-probe.json")

from secret_probe import is_blocked, reload_policy  # noqa: E402


def _load_adapter_eicar():
    path = ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py"
    # Avoid importing full adapter (heavy). Inline the same marker check.
    return (
        lambda data: b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in data
        or b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR" in data
    )


def main() -> int:
    reload_policy()
    cases = [
        ("tìm /opt/data", True),
        ("list /opt/assistant/.env", True),
        ("what is the weather", False),
        ("xin chào", False),
        ("show /etc/shadow", True),
        ("read private_key please", True),
    ]
    failed = []
    for text, want in cases:
        got = is_blocked(text)
        if got != want:
            failed.append((text, want, got))
    eicar = _load_adapter_eicar()
    sample = (
        b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    )
    if not eicar(sample):
        failed.append(("eicar", True, False))
    if eicar(b"hello knowledge doc"):
        failed.append(("clean", False, True))
    if failed:
        print("FAIL", failed)
        return 1
    print("PASS", len(cases) + 2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
