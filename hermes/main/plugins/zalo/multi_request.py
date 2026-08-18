"""Split one Zalo message that contains multiple user requests."""
from __future__ import annotations

import os
import re
from typing import List

_MAX_INDEX = 20

# Keep a numbered/labeled *schedule payload* as one turn (one cron job).
# Extra markers: ZALO_SCHEDULE_KEEP_WHOLE=term1,term2  (0/off disables).
_DEFAULT_SCHEDULE_MARKERS = (
    "hàng ngày",
    "hang ngay",
    "mỗi ngày",
    "moi ngay",
    "every day",
    "daily",
    "wakeup",
    "đặt lịch",
    "dat lich",
    "hẹn giờ",
    "hen gio",
    "nhắc nhở",
    "nhac nho",
    "nhắc tôi",
    "nhac toi",
    "định kỳ",
    "dinh ky",
    "mỗi sáng",
    "moi sang",
    "mỗi tối",
    "moi toi",
    "schedule",
    "định giờ",
    "dinh gio",
)

# "tin nhắn 1:", "message 2:", "yêu cầu 3 —" (line start or mid-sentence)
_LABELED = re.compile(
    r"(?i)"
    r"(?:tin\s+nhắn|message|msg|yêu\s+cầu|request)\s*"
    r"(?P<n>\d+)\s*"
    r"[:.\-—]\s*"
)

# Line-start indexes:
#   "1. task"  "2) task"  "1 task"  "2.Sau đó" (optional space after . or ))
_NUMBERED = re.compile(
    r"(?m)^\s*(?P<n>\d+)(?:[.)]\s*|\s+)(?P<body>.+)$"
)


def _keep_whole_enabled() -> bool:
    raw = (os.getenv("ZALO_SCHEDULE_KEEP_WHOLE") or "1").strip().lower()
    return raw not in {"0", "off", "false", "no"}


def _schedule_markers() -> List[str]:
    raw = (os.getenv("ZALO_SCHEDULE_KEEP_WHOLE") or "").strip()
    extra: List[str] = []
    if raw and raw.lower() not in {"1", "true", "yes", "on", "0", "off", "false", "no"}:
        extra = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return list(_DEFAULT_SCHEDULE_MARKERS) + extra


def looks_like_schedule_job(text: str) -> bool:
    """True when the bubble is one recurring job whose body is a task list."""
    if not _keep_whole_enabled():
        return False
    low = (text or "").lower()
    if not low.strip():
        return False
    return any(m in low for m in _schedule_markers())


def split_compound_requests(text: str) -> List[str]:
    """Return one or more non-empty request strings.

    If no compound pattern is detected, returns [text] unchanged.
    Schedule-shaped lists stay whole so one cron stores and later runs every item.
    """
    raw = (text or "").strip()
    if not raw:
        return []
    if looks_like_schedule_job(raw):
        return [raw]

    labeled = list(_LABELED.finditer(raw))
    if len(labeled) >= 2:
        parts: List[str] = []
        for i, m in enumerate(labeled):
            start = m.end()
            end = labeled[i + 1].start() if i + 1 < len(labeled) else len(raw)
            chunk = raw[start:end].strip()
            if chunk:
                parts.append(chunk)
        if len(parts) >= 2:
            return parts

    numbered = _numbered_bodies(raw)
    if len(numbered) >= 2:
        return numbered

    return [raw]


def _numbered_bodies(raw: str) -> List[str]:
    items: List[tuple[int, str]] = []
    for m in _NUMBERED.finditer(raw):
        n = int(m.group("n"))
        if 1 <= n <= _MAX_INDEX:
            body = (m.group("body") or "").strip()
            if body:
                items.append((n, body))
    if len(items) < 2:
        return []
    nums = {n for n, _ in items}
    if 1 not in nums or 2 not in nums:
        return []
    items.sort(key=lambda x: x[0])
    return [b for _, b in items]
