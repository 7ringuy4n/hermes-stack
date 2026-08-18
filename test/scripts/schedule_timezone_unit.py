# -*- coding: utf-8 -*-
"""Unit tests for schedule TZ today vs tomorrow (no VPS)."""
from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "tools"))

from schedule_tz import describe_next_run, next_daily_run  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TZ = "Asia/Ho_Chi_Minh"


def _now(h: int, m: int) -> datetime:
    tz = ZoneInfo(TZ)
    return datetime(2026, 8, 18, h, m, 0, tzinfo=tz)


def main() -> int:
    fails = 0

    # 05:58 → 06:00 same day
    nxt = next_daily_run(6, 0, now=_now(5, 58), tz_name=TZ)
    if nxt.date().day != 18:
        print("FAIL 05:58→06:00 expected today 18/08")
        fails += 1
    else:
        print("PASS 05:58->06:00 is today")

    d = describe_next_run(6, 0, now=_now(5, 58), tz_name=TZ)
    if not d["is_today"]:
        print("FAIL describe says not today")
        fails += 1
    if d.get("is_tomorrow"):
        print("FAIL describe says tomorrow at 05:58")
        fails += 1

    # 06:01 → next day
    nxt2 = next_daily_run(6, 0, now=_now(6, 1), tz_name=TZ)
    if nxt2.date().day != 19:
        print("FAIL 06:01->06:00 expected tomorrow 19/08")
        fails += 1
    else:
        print("PASS 06:01->06:00 is tomorrow")

    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
