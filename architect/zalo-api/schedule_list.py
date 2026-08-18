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
    schedule = str(
        row.get("schedule")
        or row.get("cron")
        or row.get("expression")
        or row.get("at")
        or row.get("next")
        or ""
    ).strip()
    payload = str(
        row.get("message")
        or row.get("payload")
        or row.get("prompt")
        or row.get("text")
        or row.get("description")
        or ""
    ).strip()
    payload = re.sub(r"\s+", " ", payload)[:120]
    bits = [name]
    if schedule:
        bits.append(f"@ {schedule}")
    if payload:
        bits.append(f"— {payload}")
    return " ".join(bits)[:240]


def fmt_hermes_cron_list(raw: str, *, limit: int | None = None) -> str:
    cap = limit if limit is not None else ZALO_SCHEDULE_LIST_LIMIT
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
    lines = [f"lịch Hermes ({len(shown)}/{total}):"]
    for i, row in enumerate(shown, 1):
        lines.append(f"{i}. {row}")
    rest = total - len(shown)
    if rest > 0:
        lines.append(f"… còn {rest} lịch")
    return "\n".join(lines)
