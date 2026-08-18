# -*- coding: utf-8 -*-
"""Unit tests for Zalo busy/interrupt gateway-noise filter (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from gateway_noise import is_busy_interrupt_notice  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BUSY = (
    "⚡ Interrupting current task. I'll respond to your message shortly.\n"
    "💡 First-time tip — I just interrupted my current task to answer you. "
    "Send `/busy queue` to queue follow-ups for after the current task instead, "
    "`/busy steer` to inject them mid-run without interrupting, or `/busy status` to check. "
    "This notice won't appear again."
)


def main() -> int:
    if not is_busy_interrupt_notice(BUSY):
        print("FAIL expected busy interrupt notice to be dropped")
        return 1
    if not is_busy_interrupt_notice("Interrupting current task. I'll respond shortly."):
        print("FAIL short interrupt line")
        return 1
    if is_busy_interrupt_notice("Đã xong."):
        print("FAIL result line must not be noise")
        return 1
    if is_busy_interrupt_notice("Giá xăng E5 RON92"):
        print("FAIL fuel reply must not be noise")
        return 1
    print("PASS busy interrupt dropped; user results kept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
