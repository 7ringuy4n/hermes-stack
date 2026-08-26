"""Format Hermes cron list output for Zalo admin commands."""
from __future__ import annotations

import json
import os
from typing import Any

ZALO_SCHEDULE_LIST_LIMIT = max(1, int(os.environ.get("ZALO_SCHEDULE_LIST_LIMIT", "10") or "10"))
_INTERNAL_MARKS = (
    "daily-optimize",
    "optimize-rules",
    "new-session",
    "rotate-session",
    "clearsession",
)


def _is_internal_text(s: str) -> bool:
    low = (s or "").lower().replace("_", "-")
    return any(m in low for m in _INTERNAL_MARKS)


def _redact_cron_session(line: str) -> str:
    out: list[str] = []
    i = 0
    low = line.lower()
    while True:
        j = low.find("cron_", i)
        if j < 0:
            out.append(line[i:])
            break
        out.append(line[i:j])
        k = j + 5
        while k < len(line) and (line[k].isalnum() or line[k] in "_-"):
            k += 1
        out.append("(session)")
        i = k
        low = line.lower()
    return "".join(out)


def _redact_paths(line: str) -> str:
    bits: list[str] = []
    for tok in line.split(" "):
        if tok.startswith("/opt/") or tok.startswith("/data/"):
            bits.append("(path)")
        else:
            bits.append(tok)
    return " ".join(bits)


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
    """True when the stored prompt is only a digit clock (optional CLI prefix)."""
    t = (text or "").strip()
    if not t:
        return False
    tokens = t.split(None, 1)
    if tokens[0].lower() in {"timer", "time", "schedule"} and len(tokens) > 1:
        t = tokens[1].strip()
    raw = t.lower().replace(" ", "")
    for ch in raw:
        if ch not in "0123456789:h":
            return False
    clock = raw.replace("h", ":", 1) if "h" in raw and ":" not in raw else raw.replace("h", ":")
    if clock.count(":") != 1:
        return False
    left, right = clock.split(":", 1)
    if not left.isdigit():
        return False
    if right == "":
        minute = 0
    elif right.isdigit() and len(right) <= 2:
        minute = int(right)
    else:
        return False
    hour = int(left)
    return 0 <= hour <= 23 and 0 <= minute <= 59


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
        if not line or line.lower().startswith("no scheduled job"):
            return None
        if line.lower().startswith("create one with"):
            return None
        if _is_internal_text(line):
            return None
        line = _redact_paths(_redact_cron_session(line))
        return line[:240]
    if not isinstance(row, dict):
        return None
    name = str(row.get("name") or row.get("id") or row.get("job_id") or "").strip()
    if not name or _is_internal_text(name):
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
    payload = " ".join(payload.split())[:120]
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
        return "Lịch trống hoặc không đọc được."
    first = (text.splitlines()[0] if text.splitlines() else text).strip().lower()
    if first.startswith("no scheduled job"):
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
