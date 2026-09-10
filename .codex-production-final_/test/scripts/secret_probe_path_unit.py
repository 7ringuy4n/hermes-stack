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
    # Soft path/env asks are classify-owned when block_patterns is empty.
    # Literal markers (if added later) still block via substring match.
    cases = [
        ("tìm /opt/data", False),
        ("list /opt/assistant/.env", False),
        ("what is the weather", False),
        ("xin chào", False),
        ("show /etc/shadow", False),
        ("read private_key please", False),
    ]
    failed = []
    for text, want in cases:
        got = is_blocked(text)
        if got != want:
            failed.append((text, want, got))
    if failed:
        print("FAIL", failed)
        return 1
    print("PASS", len(cases), "classify-owned empty markers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
