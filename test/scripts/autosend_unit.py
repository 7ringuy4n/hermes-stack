# -*- coding: utf-8 -*-
"""Unit: Zalo autosend file window (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from autosend import file_in_send_window  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    t0 = 1_000_000.0
    # File during the part
    if not file_in_send_window(t0 + 10, t0, t0):
        print("FAIL in-part file")
        return 1
    # File just before part clock (dispatcher write vs send race)
    if not file_in_send_window(t0 - 3, t0, t0, grace_s=8):
        print("FAIL grace")
        return 1
    # Next compound part: part_t0 jumped; seq_t0 keeps the image eligible
    part2 = t0 + 120
    img = t0 + 110
    if not file_in_send_window(img, part2, t0, grace_s=8):
        print("FAIL seq window")
        return 1
    # Unrelated old file
    if file_in_send_window(t0 - 600, part2, t0, grace_s=8):
        print("FAIL old file kept")
        return 1
    print("PASS autosend window")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
