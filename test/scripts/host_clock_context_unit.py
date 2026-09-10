# -*- coding: utf-8 -*-
"""Unit: Zalo Hermes turns get authoritative host Local now context."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from host_clock import (  # noqa: E402
    local_now_label,
    strip_host_clock_context,
    with_host_clock_context,
)
from classify_client import strip_prior_for_classify  # noqa: E402


def main() -> int:
    with patch.dict(os.environ, {"ASSISTANT_TZ": "Asia/Ho_Chi_Minh", "TZ": "Asia/Ho_Chi_Minh"}):
        stamp = local_now_label()
        assert len(stamp) >= 16 and stamp[4] == "-" and stamp[10] == " ", stamp
        ask = "thời tiết hcm ra sao"
        body = with_host_clock_context(ask)
        assert "Timezone: Asia/Ho_Chi_Minh" in body, body
        assert f"Local now: {stamp}" in body, body
        assert body.strip().endswith(ask), body
        again = with_host_clock_context(body)
        assert again.count("Local now:") == 1, again
        assert with_host_clock_context("   ") == "   "
        assert strip_host_clock_context(body) == ask, strip_host_clock_context(body)
        assert strip_prior_for_classify(body) == ask, strip_prior_for_classify(body)
        schedule_ask = (
            "2 phút nữa vẽ cho tôi hình thời tiết hồ chí minh hiện tại"
        )
        stamped_sched = with_host_clock_context(schedule_ask)
        assert strip_prior_for_classify(stamped_sched) == schedule_ask

    print("host_clock_context_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
