# -*- coding: utf-8 -*-
"""Unit: Zalo Hermes turns get authoritative host Local now context."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from host_clock import local_now_label, with_host_clock_context  # noqa: E402


def main() -> int:
    with patch.dict(os.environ, {"ASSISTANT_TZ": "Asia/Ho_Chi_Minh", "TZ": "Asia/Ho_Chi_Minh"}):
        stamp = local_now_label()
        assert len(stamp) >= 16 and stamp[4] == "-" and stamp[10] == " ", stamp
        body = with_host_clock_context("thời tiết hcm ra sao")
        assert "Timezone: Asia/Ho_Chi_Minh" in body, body
        assert f"Local now: {stamp}" in body, body
        assert body.strip().endswith("thời tiết hcm ra sao"), body
        again = with_host_clock_context(body)
        assert again.count("Local now:") == 1, again
        assert with_host_clock_context("   ") == "   "

    print("host_clock_context_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
