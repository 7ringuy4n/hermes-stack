"""Format Hermes cron list output for Zalo admin commands."""
from __future__ import annotations

import json
import os
import re
from typing import Any

ZALO_SCHEDULE_LIST_LIMIT = max(1, int(os.environ.get("ZALO_SCHEDULE_LIST_LIMIT", "10") or "10"))
_SCHEDULE_INTERNAL_RE = re.compile(
    r"daily[-_]?optimize|optimize[-_]?rules|new.?session|rotate.?session|clearsession",
    re.I,
)
_CRON_SESSION_RE = re.compile(r"cron_[a-z0-9_-]+", re.I)
_EMPTY_CRON_RE = re.compile(r"^\s*no scheduled jobs?\b", re.I)
_CLOCK_PROMPT_RE = re.compile(
    r"^(?:timer|hẹn\s*giờ|hen\s*gio|lúc|luc|at)\s+",
    re.I,
)
_HHMM_PROMPT_RE = re.compile(
    r"^\d{1,2}\s*[:h]\s*\d{2}(?:\s*(?:am|pm|sáng|sang|chiều|chieu|tối|toi))?\s*$",
    re.I,
)


def cron_expr_clock(expr: str) -> str:
    """Daily `M H * * *` → `HH:MM`; otherwise the expr as-is."""
    parts = (expr or "").split()
    if len(parts) >= 5 and parts[2] == "*" and parts[3] == "*" and parts[4] == "*":
        try:
            minute = int(parts[0])
            hour = int(parts[1])
        except ValueError:
            return (expr or "").strip()
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    return (expr or "").strip()


def schedule_clock_label(schedule: Any) -> str:
    if isinstance(schedule, dict):
        expr = str(schedule.get("expr") or schedule.get("display") or "").strip()
    else:
        expr = str(schedule or "").strip()
    if not expr:
        return ""
    return cron_expr_clock(expr)


def prompt_is_clock_only(text: str) -> bool:
    t = _CLOCK_PROMPT_RE.sub("", (text or "").strip()).strip()
    return bool(t) and bool(_HHMM_PROMPT_RE.match(t))


def schedule_destination_label(row: dict[str, Any]) -> str:
    """Human destination for list lines (e.g. ``→ nhóm LC group``)."""
    if not isinstance(row, dict):
        return ""
    origin = row.get("origin") if isinstance(row.get("origin"), dict) else {}
    context = row.get("context") if isinstance(row.get("context"), dict) else {}
    tt = str(
        context.get("thread_type")
        or origin.get("thread_type")
        or context.get("chat_type")
        or ""
    ).lower()
    name = str(
        origin.get("target_name")
        or context.get("target_channel")
        or origin.get("chat_name")
        or ""
    ).strip()
    if not name:
        return ""
    if tt in {"group", "g"} or str(context.get("chat_type") or "").lower() == "group":
        return f"→ nhóm {name}"
    if tt in {"user", "dm"} and name:
        return f"→ DM {name}"
    return f"→ {name}"


def schedule_row_label(row: Any) -> str | None:
    if isinstance(row, str):
        line = row.strip()
        if not line or _EMPTY_CRON_RE.match(line):
            return None
        if line.lower().startswith("create one with"):
            return None
        if _SCHEDULE_INTERNAL_RE.search(line):
            return None
        line = _CRON_SESSION_RE.sub("(session)", line)
        line = re.sub(r"/(?:opt|data)/[^\s]+", "(path)", line)
        return line[:240]
    if not isinstance(row, dict):
        return None
    name = str(row.get("name") or row.get("id") or row.get("job_id") or "").strip()
    if not name or _SCHEDULE_INTERNAL_RE.search(name):
        return None
    schedule = schedule_clock_label(
        row.get("schedule")
        or row.get("schedule_display")
        or row.get("cron")
        or row.get("expression")
        or row.get("at")
        or row.get("next")
        or ""
    )
    payload = str(
        row.get("message")
        or row.get("payload")
        or row.get("prompt")
        or row.get("text")
        or row.get("description")
        or ""
    ).strip()
    payload = re.sub(r"\s+", " ", payload)[:120]
    dest = schedule_destination_label(row)
    bits = [name]
    if schedule:
        bits.append(f"@ {schedule}")
    if dest:
        bits.append(dest)
    if payload and not prompt_is_clock_only(payload):
        bits.append(f"— {payload}")
    return " ".join(bits)[:240]


def fmt_hermes_cron_list(
    raw: str, *, limit: int | None = None, heading: str | None = None
) -> str:
    cap = limit if limit is not None else ZALO_SCHEDULE_LIST_LIMIT
    title = (heading or "lịch Hermes").strip() or "lịch Hermes"
    text = (raw or "").strip()
    if not text or text.lower().startswith("(no hermes cron"):
        return "Lịch trống hoặc không đọc được (Hermes chưa sẵn sàng)."
    if _EMPTY_CRON_RE.search(text.splitlines()[0] if text.splitlines() else text):
        return "Lịch trống (chưa có lịch nào)."
    rows: list[str] = []
    parsed: Any = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        items: list[Any]
        if isinstance(parsed, list):
            items = parsed
        elif isinstance(parsed, dict):
            items = (
                parsed.get("jobs")
                or parsed.get("items")
                or parsed.get("crons")
                or []
            )
            if not isinstance(items, list):
                items = [parsed]
        else:
            items = []
        for item in items:
            label = schedule_row_label(item)
            if label:
                rows.append(label)
    if not rows:
        for line in text.splitlines():
            label = schedule_row_label(line)
            if label:
                rows.append(label)
    if not rows:
        return "Lịch trống (chưa có lịch nào)."
    total = len(rows)
    shown = rows[:cap]
    lines = [f"{title} ({len(shown)}/{total}):"]
    for i, row in enumerate(shown, 1):
        lines.append(f"{i}. {row}")
    rest = total - len(shown)
    if rest > 0:
        lines.append(f"… còn {rest} lịch")
    return "\n".join(lines)
