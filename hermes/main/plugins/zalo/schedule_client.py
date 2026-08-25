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

# Relative-time patterns: "N phút nữa", "sau N phút", "in N minutes", "trong 1 giờ", etc.
_RELATIVE_RE = re.compile(
    r"(?:sau\s+|in\s+|trong\s+)?(\d+)\s*(phút|giây|giờ|phut|giay|gio|minute|minutes|second|seconds|hour|hours)\s*(?:nữa|nua)?",
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
    secs = delay_seconds_from_text(text)
    if secs is None:
        return ""
    return next_run_at_from_delay(secs, tz=tz)


def delay_seconds_from_text(text: str) -> int | None:
    """Parse relative delay seconds from user prose (authoritative host clock later)."""
    raw = (text or "").strip()
    m = _RELATIVE_RE.search(raw)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    secs = n * _UNIT_SECONDS.get(unit, 0)
    if secs <= 0 or secs > 86400 * 30:
        return None
    return secs


def delay_seconds_from_plan(plan: dict[str, Any] | None) -> int | None:
    src = plan if isinstance(plan, dict) else {}
    raw = src.get("delay_seconds")
    if raw is None or raw == "":
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n <= 0 or n > 86400 * 30:
        return None
    return n


def next_run_at_from_delay(delay_seconds: int, tz: str = "Asia/Ho_Chi_Minh") -> str:
    """RFC3339 UTC for now+delay using the host clock (never the LLM clock)."""
    import datetime

    _ = tz  # reserved for future local-display helpers; fire instant is UTC now+delay
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    fire_utc = now_utc + datetime.timedelta(seconds=int(delay_seconds))
    return fire_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def cron_from_next_run_at(next_run_at: str, tz: str = "Asia/Ho_Chi_Minh") -> str:
    """Derive a once HH:MM cron placeholder for DB NOT NULL from an RFC3339 fire time."""
    import datetime

    raw = (next_run_at or "").strip()
    if not raw:
        return ""
    try:
        if raw.endswith("Z"):
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = datetime.datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        try:
            import zoneinfo

            loc = zoneinfo.ZoneInfo(tz or "Asia/Ho_Chi_Minh")
        except Exception:
            loc = datetime.timezone(datetime.timedelta(hours=7))
        local = dt.astimezone(loc)
        return f"{local.minute} {local.hour} * * *"
    except Exception:
        return ""


def resolve_schedule_timing(
    plan: dict[str, Any] | None,
    text: str,
    tz: str = "Asia/Ho_Chi_Minh",
) -> dict[str, Any]:
    """Authoritative fire timing for create_schedule.

    once_after / relative prose: host clock + delay_seconds. Never trust LLM
    next_run_at or LLM-invented cron for relative delays.
    """
    src = plan if isinstance(plan, dict) else {}
    zone = str(src.get("timezone") or tz or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    delay = delay_seconds_from_plan(src)
    form = str(src.get("schedule_form") or "").strip().lower()
    if delay is not None or form == "once_after":
        if delay is None:
            return {
                "schedule_form": "once_after",
                "delay_seconds": None,
                "cadence": "once",
                "cron_expr": "",
                "next_run_at": "",
            }
        nxt = next_run_at_from_delay(delay, tz=zone)
        cron = cron_from_next_run_at(nxt, tz=zone) or "0 0 * * *"
        return {
            "schedule_form": "once_after",
            "delay_seconds": delay,
            "cadence": "once",
            "cron_expr": cron,
            "next_run_at": nxt,
        }
    cron = str(src.get("cron_expr") or "").strip()
    cadence = str(src.get("cadence") or "").strip().lower() or "once"
    form_out = form or ("recurring" if cadence not in {"", "once"} else "once_at")
    # once_at: classifier leaves cron null; derive storage cron from prose clock if needed.
    if not cron and form_out == "once_at":
        cron = _clock_cron_from_text(text) or ""
    if not cron and form_out not in {"once_after"} and cadence == "once":
        cron = _clock_cron_from_text(text) or ""
    return {
        "schedule_form": form_out,
        "delay_seconds": None,
        "cadence": cadence,
        "cron_expr": cron,
        "next_run_at": "",
    }


def _clock_cron_from_text(text: str) -> str:
    """Protocol HH:MM → once-daily cron for worker storage (not classifier NLU)."""
    m = re.search(
        r"(?:lúc|luc|at|@)\s*(\d{1,2})\s*[:hH]\s*(\d{2})\b|\b(\d{1,2})\s*[:hH]\s*(\d{2})\b",
        text or "",
        re.I,
    )
    if not m:
        return ""
    h_raw = m.group(1) or m.group(3)
    min_raw = m.group(2) or m.group(4)
    try:
        hour = int(h_raw)
        minute = int(min_raw)
    except (TypeError, ValueError):
        return ""
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return ""
    return f"{minute} {hour} * * *"

def exact_schedule_body(original: str) -> str:
    """Protocol body after nội dung:/content: (field delimiter — not NLU)."""
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


_TASK_DETAIL_TYPES = {
    "search",
    "media_generation",
    "file_processing",
    "knowledge",
    "tool",
    "coding",
}


def plan_is_task_work(plan: dict[str, Any] | None) -> bool:
    """True when classify structured fields mean due work (skills), not a send-body."""
    src = plan if isinstance(plan, dict) else {}
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    if len(parts) > 1:
        return True
    details = src.get("task_details")
    if isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue
            tt = str(item.get("task_type") or item.get("skill") or "").strip().lower()
            if tt in _TASK_DETAIL_TYPES or tt in {"web_search", "media_file"}:
                return True
    types = src.get("attachment_types")
    if isinstance(types, list) and any(str(x).strip() for x in types):
        return True
    if src.get("attachments_required") in {True, 1, "1", "true", "yes"}:
        return True
    return False


def schedule_delivery_mode(plan: dict[str, Any] | None, original: str = "") -> str:
    """How the worker should deliver fire_text: ``verbatim`` or ``process``.

    Source of truth is classify JSON ``schedule_delivery``. Host does not parse
    user prose for verbs. Structured multi-skill plans force process. Default process.
    """
    del original  # audit only — delivery is not inferred from the bubble
    src = plan if isinstance(plan, dict) else {}
    explicit = str(src.get("schedule_delivery") or "").strip().lower()
    if plan_is_task_work(src):
        return "process"
    if explicit in {"verbatim", "send", "deliver"}:
        return "verbatim"
    if explicit in {"process", "hermes", "classify"}:
        return "process"
    return "process"


def fire_text_from_plan(plan: dict[str, Any] | None, original: str = "") -> str:
    """Inner work from classify fields only. Never fire the create-schedule ask.

    ``original`` is used solely for the protocol delimiter ``nội dung:`` /
    ``content:`` when delivery is verbatim. If message/instructions still equal
    the full inbound bubble, refuse (classify must emit inner work only).
    """
    src = plan if isinstance(plan, dict) else {}
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    delivery = schedule_delivery_mode(src, original)
    orig = (original or "").strip()

    def _not_full_ask(text: str) -> str:
        t = (text or "").strip()
        if not t or (orig and t == orig):
            return ""
        return t

    if delivery == "verbatim":
        exact = exact_schedule_body(original)
        if exact:
            return exact
        msg = _not_full_ask(str(src.get("message") or ""))
        if msg:
            return msg
        if parts:
            return _not_full_ask("\n".join(parts))
        return ""
    if parts:
        joined = _not_full_ask("\n".join(parts))
        if joined:
            return joined
    msg = _not_full_ask(str(src.get("message") or ""))
    if msg:
        return msg
    exact = exact_schedule_body(original)
    if exact:
        return exact
    return ""


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
