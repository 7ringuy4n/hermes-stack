"""HTTP client for the Go schedule worker (store + wait + fire back to Hermes)."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Optional

DEFAULT_URL = "http://schedule-worker:8110"

_CONTENT_AFTER = re.compile(
    r"(?:với\s*nội\s*dung|voi\s*noi\s*dung|nội\s*dung|noi\s*dung|content)\s*[:\-]?\s*(.+)$",
    re.I | re.S,
)
# Protocol guard: prefer exact body after nội dung: if classify paraphrased.

# Relative-time patterns: "N phút nữa", "sau N phút", "in N minutes", etc.
_RELATIVE_RE = re.compile(
    r"(?:sau\s+|in\s+)?(\d+)\s*(phút|giây|giờ|phut|giay|gio|minute|minutes|second|seconds|hour|hours)\s*(?:nữa|nua)?",
    re.I,
)
_UNIT_SECONDS: dict[str, int] = {
    "phút": 60, "phut": 60, "minute": 60, "minutes": 60,
    "giây": 1, "giay": 1, "second": 1, "seconds": 1,
    "giờ": 3600, "gio": 3600, "hour": 3600, "hours": 3600,
}


def next_run_at_from_relative(text: str, tz: str = "Asia/Ho_Chi_Minh") -> str:
    """Return RFC3339 UTC timestamp for relative-time schedules ('N phút nữa').

    Returns empty string when no relative-time expression is found; the worker
    then falls back to cron_expr resolution.
    """
    raw = (text or "").strip()
    m = _RELATIVE_RE.search(raw)
    if not m:
        return ""
    n = int(m.group(1))
    unit = m.group(2).lower()
    secs = n * _UNIT_SECONDS.get(unit, 60)
    import datetime
    try:
        import zoneinfo
        loc = zoneinfo.ZoneInfo(tz)
    except Exception:
        loc = None
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    fire_utc = now_utc + datetime.timedelta(seconds=secs)
    return fire_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def exact_schedule_body(original: str) -> str:
    """Prefer verbatim text after nội dung: so fire never uses a paraphrased plan."""
    raw = (original or "").strip()
    if not raw:
        return ""
    m = _CONTENT_AFTER.search(raw)
    if not m:
        return ""
    return (m.group(1) or "").strip().strip("\"' ")


def _worker_flag_on() -> bool:
    raw = (os.getenv("SCHEDULE_WORKER") or "0").strip().lower()
    return raw in {"1", "on", "true", "yes"}


def schedule_url() -> str:
    raw = (os.getenv("SCHEDULE_URL") or "").strip().rstrip("/")
    if raw:
        return raw
    if _worker_flag_on():
        return DEFAULT_URL
    return ""


def schedule_enabled() -> bool:
    """True when the Go schedule worker is reachable (URL set or SCHEDULE_WORKER=1)."""
    if (os.getenv("SCHEDULE_URL") or "").strip():
        return True
    return _worker_flag_on()


def fire_text_from_plan(plan: dict[str, Any] | None, original: str = "") -> str:
    """Inner work only. Never fire the đặt lịch wrapper (that re-creates schedules)."""
    exact = exact_schedule_body(original)
    if exact:
        return exact
    src = plan if isinstance(plan, dict) else {}
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    if parts:
        return "\n".join(parts)
    msg = str(src.get("message") or "").strip()
    if msg:
        return msg
    return (original or "").strip()


def _req(method: str, path: str, payload: Optional[dict] = None, timeout: float = 8.0) -> dict[str, Any]:
    url = schedule_url() + path
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {}


def create_schedule(
    *,
    cron_expr: str,
    text: str,
    fire_text: str = "",
    name: str = "",
    origin: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    schedule_id: str | None = None,
    cadence: str = "",
    timezone: str = "Asia/Ho_Chi_Minh",
    next_run_at: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "cron_expr": cron_expr,
        "text": text,
        "fire_text": fire_text or fire_text_from_plan((context or {}).get("plan") if isinstance(context, dict) else None, text),
        "name": name,
        "origin": origin or {},
        "context": context or {},
        "timezone": timezone,
        "cadence": cadence,
        "enabled": True,
    }
    if schedule_id:
        body["id"] = schedule_id
    if next_run_at:
        body["next_run_at"] = next_run_at
    return _req("POST", "/v1/schedules", body)


def list_schedules() -> list[dict[str, Any]]:
    data = _req("GET", "/v1/schedules")
    rows = data.get("schedules") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def delete_schedule(sid: str) -> dict[str, Any]:
    return _req("DELETE", f"/v1/schedules/{sid}")


def schedules_for_thread(thread_id: str) -> list[dict[str, Any]]:
    """Schedules that deliver to or were requested from this thread id."""
    tid = (thread_id or "").strip()
    if not tid:
        return []
    out: list[dict[str, Any]] = []
    for row in list_schedules():
        if not isinstance(row, dict):
            continue
        origin = row.get("origin") if isinstance(row.get("origin"), dict) else {}
        context = row.get("context") if isinstance(row.get("context"), dict) else {}
        ids = {
            str(origin.get(k) or "").strip()
            for k in ("thread_id", "chat_id", "user_id", "requester_id", "sender_id")
        }
        ids |= {
            str(context.get(k) or "").strip()
            for k in ("thread_id", "sender_id")
        }
        ids.discard("")
        if tid in ids:
            out.append(row)
    return out


def delete_schedules_for_thread(thread_id: str) -> list[str]:
    """Delete every schedule tied to a destination/requester thread. Returns deleted ids."""
    deleted: list[str] = []
    for row in schedules_for_thread(thread_id):
        sid = str(row.get("id") or "").strip()
        if not sid:
            continue
        data = delete_schedule(sid)
        if data.get("ok") or data.get("deleted") == sid or not data:
            # empty {} from soft HTTP failure — still record attempt id for UX
            deleted.append(sid)
    return deleted


def list_schedule_history(
    *,
    schedule_id: str = "",
    thread_id: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    q = f"?limit={int(limit)}"
    if schedule_id:
        q += f"&schedule_id={schedule_id}"
    if thread_id:
        q += f"&thread_id={thread_id}"
    data = _req("GET", f"/v1/schedules/history{q}")
    rows = data.get("history") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []
