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
    "hằng ngày",
    "hang ngay",
    "mỗi ngày",
    "moi ngay",
    "every day",
    "daily",
    "wakeup",
    "thức dậy",
    "thuc day",
    "nhắc thức",
    "nhac thuc",
    "đặt lịch",
    "dat lich",
    "một lần",
    "mot lan",
    "weekly",
    "monthly",
    "yearly",
    "hàng tuần",
    "hang tuan",
    "hàng tháng",
    "hang thang",
    "hàng năm",
    "hang nam",
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
    "gmt+7",
    "gmt +7",
)

# Numbered list + clock/GMT (06:00 GMT+7) even if a spelling is missing above.
_CLOCK_HINT = re.compile(
    r"(?i)(?:\d{1,2}\s*[:h]\s*\d{2}\s*(?:am|pm|sáng|sang|chiều|chieu|tối|toi|gmt)|gmt\s*\+?\s*7)"
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
    raw = text or ""
    low = raw.lower()
    if not low.strip():
        return False
    if any(m in low for m in _schedule_markers()):
        return True
    numbered = _numbered_bodies(raw)
    if len(numbered) >= 2 and _CLOCK_HINT.search(low):
        return True
    return False


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


def wrap_compound_part(index: int, total: int, body: str) -> str:
    """Stop the model from treating leftover list context as extra work."""
    text = (body or "").strip()
    if not text:
        return text
    return (
        f"Yêu cầu {index}/{total} — chỉ làm đúng việc này, rồi dừng. "
        f"Không làm các mục khác.\n{text}"
    )


def plan_instructions(text: str) -> List[str]:
    """Explode numbered/labeled lists into jobs. Ignores schedule keep-whole."""
    raw = (text or "").strip()
    if not raw:
        return []
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


def _finalize_numbered(items: List[tuple[int, str]]) -> List[str]:
    if len(items) < 2:
        return []
    nums = {n for n, _ in items}
    if 1 not in nums or 2 not in nums:
        return []
    items.sort(key=lambda x: x[0])
    out: List[str] = []
    seen: set[int] = set()
    for n, body in items:
        if n in seen:
            continue
        seen.add(n)
        out.append(body)
    return out


def _numbered_bodies(raw: str) -> List[str]:
    items: List[tuple[int, str]] = []
    for m in _NUMBERED.finditer(raw):
        n = int(m.group("n"))
        if 1 <= n <= _MAX_INDEX:
            body = (m.group("body") or "").strip()
            if body:
                items.append((n, body))
    line = _finalize_numbered(items)
    if len(line) >= 2:
        return line
    return _inline_numbered_bodies(raw)


def _inline_numbered_bodies(raw: str) -> List[str]:
    """Zalo often flattens lists to one line: 'Thực hiện: 1. … 2. … 3. …'."""
    marks: List[tuple[int, int, int]] = []
    for m in re.finditer(r"(?:^|(?<=\n)|(?<=[\s:]))(\d+)[.)]\s*", raw or ""):
        n = int(m.group(1))
        if 1 <= n <= _MAX_INDEX:
            marks.append((n, m.end(), m.start()))
    if len(marks) < 2:
        return []
    items: List[tuple[int, str]] = []
    for i, (n, body_start, _tok) in enumerate(marks):
        end = marks[i + 1][2] if i + 1 < len(marks) else len(raw)
        body = (raw[body_start:end] or "").strip()
        if body:
            items.append((n, body))
    return _finalize_numbered(items)
