"""Timezone-aware daily schedule helpers (Asia/Ho_Chi_Minh default).

Used by skills/tests — Hermes `hermes cron` still owns execution; this module
answers "today or tomorrow?" for a fixed local clock time.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TZ = os.environ.get("TZ", "Asia/Ho_Chi_Minh")


def local_zone(tz_name: str | None = None) -> ZoneInfo:
    return ZoneInfo(tz_name or DEFAULT_TZ)


def parse_hhmm(text: str) -> time | None:
    """Parse 6:00, 06:00, 6:00 AM, 18h30, 6h."""
    t = (text or "").strip().lower()
    m = re.search(
        r"(?P<h>\d{1,2})\s*(?:[:h]\s*(?P<m>\d{2}))?\s*(?P<ampm>am|pm|sáng|chiều|tối)?",
        t,
    )
    if not m:
        return None
    hour = int(m.group("h"))
    minute = int(m.group("m") or 0)
    ampm = (m.group("ampm") or "").lower()
    if ampm in {"pm", "chiều", "tối"} and hour < 12:
        hour += 12
    if ampm in {"am", "sáng"} and hour == 12:
        hour = 0
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
