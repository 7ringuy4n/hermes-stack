"""CRUD for Hermes jobs.json (shared cron dir). User-facing: lịch / schedule."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from schedule_list import (
    ZALO_SCHEDULE_LIST_LIMIT,
    fmt_hermes_cron_list,
    schedule_row_label,
)

JOBS_NAME = "jobs.json"
_CRON5_RE = re.compile(
    r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(\S+))?\s*$"
)
_HHMM_RE = re.compile(
    r"^(?P<h>\d{1,2})\s*[:h]\s*(?P<m>\d{2})?\s*(?P<ampm>am|pm|sáng|chiều|tối)?$",
    re.I,
)
_INTERNAL_RE = re.compile(
    r"daily[-_]?optimize|optimize[-_]?rules|new.?session|rotate.?session|clearsession",
    re.I,
)


def _now_iso(tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return datetime.now(tz).isoformat()


def jobs_file(data_dir: str) -> Path:
    return Path(data_dir) / "cron" / JOBS_NAME


def load_bundle(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"jobs": [], "updated_at": None}
    try:
        data = __import__("json").loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"jobs": [], "updated_at": None}
    if isinstance(data, dict):
        jobs = data.get("jobs") if isinstance(data.get("jobs"), list) else []
        return {"jobs": [j for j in jobs if isinstance(j, dict)], "updated_at": data.get("updated_at")}
    if isinstance(data, list):
        return {"jobs": [j for j in data if isinstance(j, dict)], "updated_at": None}
    return {"jobs": [], "updated_at": None}


def save_bundle(path: Path, jobs: list[dict[str, Any]], tz_name: str) -> None:
    """Write jobs.json (zalo-api image — no backup-restore import)."""
    import json
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"jobs": jobs, "updated_at": _now_iso(tz_name)}
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="jobs.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(raw)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def visible_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for job in jobs:
        label = schedule_row_label(job)
        if not label:
            continue
        name = str(job.get("name") or job.get("id") or "")
        prompt = str(job.get("prompt") or "")
        if _INTERNAL_RE.search(name) or _INTERNAL_RE.search(prompt):
            continue
        out.append(job)
    return out


def parse_hhmm_cron(text: str) -> Optional[str]:
    t = (text or "").strip().lower()
    m = _HHMM_RE.match(t)
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
    return f"{minute} {hour} * * *"


def parse_cron_expr(text: str) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None
    hhmm = parse_hhmm_cron(t)
    if hhmm:
        return hhmm
    m = _CRON5_RE.match(t)
    if m:
        parts = [p for p in m.groups() if p is not None]
        if len(parts) >= 5:
            return " ".join(parts[:5])
    return None


def split_add_args(rest: str) -> tuple[Optional[str], str, str]:
    """Return (cron_expr, name, prompt)."""
    raw = (rest or "").strip()
    if not raw:
        return None, "", ""
    name = ""
    if " -- " in raw:
        left, prompt = raw.split(" -- ", 1)
        left, prompt = left.strip(), prompt.strip()
    else:
        left, prompt = raw, ""
    tokens = left.split()
    # 5-field cron at start
    if len(tokens) >= 5 and all(re.match(r"^[\d*/,-]+$", t) or t == "*" for t in tokens[:5]):
        expr = " ".join(tokens[:5])
        leftover = " ".join(tokens[5:]).strip()
        if leftover and not prompt:
            prompt = leftover
        elif leftover:
            name = leftover
        return expr, name, prompt
    # HH:MM then the rest is prompt (or name + prompt)
    if tokens:
        expr = parse_hhmm_cron(tokens[0])
        if expr:
            leftover = " ".join(tokens[1:]).strip()
            if leftover and not prompt:
                prompt = leftover
            elif leftover:
                name = leftover
            return expr, name, prompt
    expr = parse_cron_expr(left)
    return expr, name, prompt


def resolve_job(jobs: list[dict[str, Any]], sel: str) -> tuple[Optional[dict[str, Any]], str]:
    s = (sel or "").strip()
    if not s:
        return None, "usage: !zalo schedule show|update|remove <số|tên>"
    visible = visible_jobs(jobs)
    if s.isdigit():
        idx = int(s)
        if 1 <= idx <= len(visible):
            return visible[idx - 1], ""
        return None, f"Không có lịch số {idx} (đang có {len(visible)})."
    sl = s.lower()
    for job in visible:
        name = str(job.get("name") or "").lower()
        jid = str(job.get("id") or "").lower()
        if sl == name or sl == jid or sl in name:
            return job, ""
    return None, f"Không tìm thấy lịch “{s}”."


def new_job(
    *,
    prompt: str,
    expr: str,
    name: str = "",
    tz_name: str = "Asia/Ho_Chi_Minh",
    sender: str = "",
    thread: str = "",
    sender_name: str = "",
) -> dict[str, Any]:
    jid = secrets.token_hex(6)
    display = expr
    return {
        "id": jid,
        "name": (name or prompt[:24] or jid).strip(),
        "prompt": prompt.strip(),
        "skills": [],
        "skill": None,
        "model": None,
        "provider": None,
        "provider_snapshot": None,
        "model_snapshot": None,
        "base_url": None,
        "script": None,
        "no_agent": False,
        "monitor_script": None,
        "monitor_url": None,
        "monitor_state": None,
        "context_from": None,
        "schedule": {"kind": "cron", "expr": expr, "display": display},
        "schedule_display": display,
        "repeat": {"times": None, "completed": 0},
        "enabled": True,
        "state": "scheduled",
        "paused_at": None,
        "paused_reason": None,
        "created_at": _now_iso(tz_name),
        "deliver": "origin",
        "origin": {
            "platform": "zalo",
            "chat_id": thread or sender,
            "chat_name": sender_name or "",
            "thread_id": thread or None,
            "user_id": sender or None,
        },
        "workdir": None,
        "enabled_toolsets": None,
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "last_delivery_error": None,
        "next_run_at": None,
        "fire_claim": None,
        "run_claim": None,
    }


def fmt_show(job: dict[str, Any]) -> str:
    label = schedule_row_label(job) or str(job.get("name") or "lịch")
    prompt = re.sub(r"\s+", " ", str(job.get("prompt") or "")).strip()
    enabled = "bật" if job.get("enabled") else "tắt"
    state = str(job.get("state") or "")
    lines = [label, f"trạng thái: {enabled}" + (f" / {state}" if state else "")]
    if prompt:
        lines.append(prompt[:500])
    return "\n".join(lines)


def fmt_list(jobs: list[dict[str, Any]], *, limit: int | None = None) -> str:
    cap = limit if limit is not None else ZALO_SCHEDULE_LIST_LIMIT
    return fmt_hermes_cron_list(
        __import__("json").dumps(visible_jobs(jobs), ensure_ascii=False),
        limit=cap,
    )


USAGE = (
    "!zalo schedule list\n"
    "!zalo schedule show <số|tên>\n"
    "!zalo schedule add <lịch> <nội dung>\n"
    "  ví dụ: !zalo schedule add 6:00 Gửi giá xăng\n"
    "  ví dụ: !zalo schedule add 0 6 * * * Gửi giá xăng\n"
    "!zalo schedule update <số|tên> --time 7:00\n"
    "!zalo schedule update <số|tên> -- <nội dung mới>\n"
    "!zalo schedule remove <số|tên>"
)
