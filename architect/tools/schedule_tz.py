"""Timezone-aware daily schedule helpers (Asia/Ho_Chi_Minh default).

Used by skills/tests — Hermes `hermes cron` still owns execution; this module
answers "today or tomorrow?" for a fixed local clock time.
"""
from __future__ import annotations

import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TZ = os.environ.get("TZ", "Asia/Ho_Chi_Minh")


def local_zone(tz_name: str | None = None) -> ZoneInfo:
    return ZoneInfo(tz_name or DEFAULT_TZ)


def parse_hhmm(text: str) -> time | None:
    """Parse digit clocks only: 6:00, 06:00, 18h30, 6h. No language am/pm words."""
    raw = (text or "").strip().lower().replace(" ", "")
    if not raw:
        return None
    for ch in raw:
        if ch not in "0123456789:h":
            return None
    clock = raw.replace("h", ":", 1) if "h" in raw and ":" not in raw else raw
    if clock.count(":") != 1:
        return None
    left, right = clock.split(":", 1)
    if not left.isdigit():
        return None
    hour = int(left)
    if right == "":
        minute = 0
    elif right.isdigit() and len(right) <= 2:
        minute = int(right)
    else:
        return None
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def next_daily_run(
    hour: int,
    minute: int = 0,
    *,
    now: datetime | None = None,
    tz_name: str | None = None,
) -> datetime:
    """Next occurrence of HH:MM in local TZ.

    If today's HH:MM is still in the future (>= now), return today.
    Otherwise return tomorrow. Matches user expectation at 05:58 for 06:00 → today.
    """
    tz = local_zone(tz_name)
    now = (now or datetime.now(tz)).astimezone(tz)
    target = datetime.combine(now.date(), time(hour, minute), tzinfo=tz)
    if target >= now:
        return target
    return target + timedelta(days=1)


def describe_next_run(
    hour: int,
    minute: int = 0,
    *,
    now: datetime | None = None,
    tz_name: str | None = None,
) -> dict[str, str | bool]:
    """Human-facing summary for cron setup replies."""
    tz = local_zone(tz_name)
    now = (now or datetime.now(tz)).astimezone(tz)
    nxt = next_daily_run(hour, minute, now=now, tz_name=tz_name)
    today = now.date()
    is_today = nxt.date() == today
    return {
        "tz": str(tz),
        "now_local": now.strftime("%H:%M %d/%m/%Y"),
        "next_run_local": nxt.strftime("%H:%M %d/%m/%Y"),
        "is_today": is_today,
        "is_tomorrow": nxt.date() == today + timedelta(days=1),
    }
