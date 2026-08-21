# -*- coding: utf-8 -*-
"""Unit: secret-probe path blocks (no local AV/EICAR in adapter)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

os.environ["SECRET_PROBE_POLICY"] = str(ROOT / "config" / "agent" / "secret-probe.json")

from secret_probe import is_blocked, reload_policy  # noqa: E402


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
    if failed:
        print("FAIL", failed)
        return 1
    print("PASS", len(cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
