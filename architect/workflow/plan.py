"""Turn natural-language requests into generic job instructions.

No business task types. Numbered/labeled lists become independent instructions.
Schedule-shaped text is still exploded into instructions (cron creates jobs).
"""
from __future__ import annotations

import re
from typing import List, Optional

_MAX_INDEX = 20
_LABELED = re.compile(
    r"(?i)(?:tin\s+nhắn|message|msg|yêu\s+cầu|request)\s*(?P<n>\d+)\s*[:.\-—]\s*"
)
_NUMBERED = re.compile(r"(?m)^\s*(?P<n>\d+)(?:[.)]\s*|\s+)(?P<body>.+)$")
_HHMM = re.compile(
    r"(?P<h>\d{1,2})\s*[:h]\s*(?P<m>\d{2})?\s*(?P<ampm>am|pm|sáng|sang|chiều|chieu|tối|toi|gmt)?",
    re.I,
)
_SCHED_CLOCK = re.compile(
    r"(?i)(?:lúc|luc|at|vào|vao|timer|time)\s*"
    r"(?P<h>\d{1,2})\s*[:h]\s*(?P<m>\d{2})"
    r"(?:\s*(?P<ampm>am|pm|sáng|sang|chiều|chieu|tối|toi))?"
)
_CRON5 = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$")


def plan_instructions(text: str) -> List[str]:
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


def wrap_instruction(index: int, total: int, body: str) -> str:
    text = (body or "").strip()
    if total <= 1:
        return text
    return (
        f"Yêu cầu {index}/{total} — chỉ làm đúng việc này, rồi dừng. "
        f"Không làm các mục khác.\n{text}"
    )


def parse_hhmm_cron(text: str) -> Optional[str]:
    t = (text or "").strip().lower()
    m = re.match(
        r"^(?P<h>\d{1,2})\s*[:h]\s*(?P<m>\d{2})?\s*"
        r"(?P<ampm>am|pm|sáng|sang|chiều|chieu|tối|toi)?$",
        t,
        re.I,
    )
    if not m:
        return None
    hour = int(m.group("h"))
    minute = int(m.group("m") or 0)
    ampm = (m.group("ampm") or "").lower()
    if ampm in {"pm", "chiều", "chieu", "tối", "toi"} and hour < 12:
        hour += 12
    if ampm in {"am", "sáng", "sang"} and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{minute} {hour} * * *"


def extract_cron_expr(text: str) -> Optional[str]:
    raw = (text or "").strip()
    m5 = _CRON5.match(raw)
    if m5:
        parts = raw.split()
        if len(parts) >= 5 and all(re.match(r"^[\d*/,-]+$", p) or p == "*" for p in parts[:5]):
            return " ".join(parts[:5])
    # Prefer the clock next to lúc/at/vào so body items like "6:00 AM" do not win.
    headed = _SCHED_CLOCK.search(raw)
    if headed:
        hour = int(headed.group("h"))
        minute = int(headed.group("m") or 0)
        ampm = (headed.group("ampm") or "").lower()
        if ampm in {"pm", "chiều", "chieu", "tối", "toi"} and hour < 12:
            hour += 12
        if ampm in {"am", "sáng", "sang"} and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{minute} {hour} * * *"
    found = list(_HHMM.finditer(raw))
    for m in found:
        chunk = m.group(0)
        expr = parse_hhmm_cron(re.sub(r"\s*gmt.*$", "", chunk, flags=re.I).strip())
        if expr:
            return expr
    return parse_hhmm_cron(raw)


def _finalize(items: List[tuple[int, str]]) -> List[str]:
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
    line = _finalize(items)
    if len(line) >= 2:
        return line
    marks: List[tuple[int, int, int]] = []
    for m in re.finditer(r"(?:^|(?<=\n)|(?<=[\s:]))(\d+)[.)]\s*", raw or ""):
        n = int(m.group(1))
        if 1 <= n <= _MAX_INDEX:
            marks.append((n, m.end(), m.start()))
    if len(marks) < 2:
        return []
    items = []
    for i, (n, body_start, _tok) in enumerate(marks):
        end = marks[i + 1][2] if i + 1 < len(marks) else len(raw)
        body = (raw[body_start:end] or "").strip()
        if body:
            items.append((n, body))
    return _finalize(items)
