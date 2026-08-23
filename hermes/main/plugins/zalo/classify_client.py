"""HTTP client for model-router POST /v1/classify.

Application code consumes structured JSON only. Tests may inject set_planner.
Keep in sync with gateway and Zalo copies.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

Planner = Callable[..., dict[str, Any]]
_planner: Planner | None = None

TASK_HINTS = ("normal", "schedule", "coding", "tool", "search", "file", "knowledge", "unknown")
CADENCES = ("once", "daily", "weekly", "monthly", "yearly")
EXECUTION_CLASSES = ("interactive", "async", "schedule")
TASK_TYPES = (
    "chat",
    "media_generation",
    "file_processing",
    "create_schedule",
    "knowledge",
    "search",
    "tool",
    "coding",
)
RESPONSE_MODES = ("direct", "ack_then_deliver", "confirm")
ATTACHMENT_TYPES = ("image", "file", "audio", "video")
SKILLS = ("media_file", "web_search", "schedule", "security", "knowledge")
HINT_SKILL = {
    "search": ("web_search", "search"),
    "schedule": ("schedule", "create"),
    "file": ("media_file", "process_file"),
    "knowledge": ("knowledge", "lookup"),
}
HINT_EXECUTION = {
    "schedule": ("schedule", "create_schedule", "confirm"),
    "file": ("async", "file_processing", "ack_then_deliver"),
    "knowledge": ("interactive", "knowledge", "ack_then_deliver"),
    "coding": ("interactive", "coding", "ack_then_deliver"),
    "search": ("async", "search", "ack_then_deliver"),
    "normal": ("interactive", "chat", "ack_then_deliver"),
    "unknown": ("interactive", "chat", "ack_then_deliver"),
    "tool": ("interactive", "tool", "ack_then_deliver"),
}
HINT_ALIASES = {"chat": "normal", "qna": "normal", "question": "normal", "general": "normal"}
MAX_INSTRUCTIONS = 32
CRON_CHARS = set("0123456789*,/-")
DEFAULT_TIMEOUT_S = 70.0
HTTP_ATTEMPTS = 1


def sanitize_instructions(raw: Any, fallback: str) -> list[str]:
    items: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            s = str(item).strip()
            if s:
                items.append(s)
    if len(items) > 3 and len(set(items)) == 1:
        items = [items[0]]
    out: list[str] = []
    seen: set[str] = set()
    for s in items:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= MAX_INSTRUCTIONS:
            break
    fb = (fallback or "").strip()
    if not out and fb:
        return [fb]
    return out


def set_planner(fn: Planner | None) -> None:
    global _planner
    _planner = fn


def valid_cron(expr: str) -> str | None:
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return None
    for p in parts:
        if not p or any(ch not in CRON_CHARS for ch in p):
            return None
    return " ".join(parts)


def normalize_execution(
    src: dict[str, Any], hint: str, *, wrapper: bool = True
) -> tuple[str, str, str]:
    raw_cls = str(src.get("execution_class") or "").strip().lower()
    raw_type = str(src.get("task_type") or "").strip().lower()
    raw_mode = str(src.get("response_mode") or "").strip().lower()
    if raw_mode == "direct":
        raw_mode = "ack_then_deliver"
    d_cls, d_type, d_mode = HINT_EXECUTION.get(hint, ("interactive", "chat", "ack_then_deliver"))
    if raw_type not in TASK_TYPES:
        raw_type = d_type
    if raw_cls not in EXECUTION_CLASSES:
        raw_cls = d_cls
        if hint == "tool" and raw_type == "media_generation":
            raw_cls = "async"
    if raw_mode not in RESPONSE_MODES:
        raw_mode = d_mode
        if raw_cls == "async":
            raw_mode = "ack_then_deliver"
        elif raw_cls == "schedule":
            raw_mode = "confirm"
    if wrapper and hint == "schedule":
        return "schedule", "create_schedule", "confirm"
    return raw_cls, raw_type, raw_mode


def normalize_depends(raw: Any, index: int) -> list[int]:
    nums: list[int] = []
    if not isinstance(raw, list):
        return []
    for item in raw:
        try:
            nums.append(int(item))
        except (TypeError, ValueError):
            continue
    out: list[int] = []
    for v in nums:
        if 0 <= v < index and v not in out:
            out.append(v)
    return out


def normalize_task_details(
    src: dict[str, Any],
    instructions: list[str],
    hint: str,
) -> list[dict[str, Any]]:
    n = len(instructions)
    raw = src.get("task_details")
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            rows.append(item if isinstance(item, dict) else {})
    while len(rows) < n:
        rows.append({})
    rows = rows[:n]
    details: list[dict[str, Any]] = []
    for i, item in enumerate(rows):
        if item:
            body = item
        elif hint == "schedule":
            body = {"execution_class": "interactive", "task_type": "chat", "response_mode": "ack_then_deliver"}
        else:
            body = src
        cls, typ, mode = normalize_execution(body, hint, wrapper=False)
        details.append(
            {
                "execution_class": cls,
                "task_type": typ,
                "response_mode": mode,
                "depends_on": normalize_depends(item.get("depends_on") if item else [], i),
            }
        )
    return details


def normalize_attachment_types(raw: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        val = str(item).strip().lower()
        if val in ATTACHMENT_TYPES and val not in out:
            out.append(val)
    return out


def normalize_skill(src: dict[str, Any], hint: str, task_type: str) -> tuple[str | None, str | None]:
    skill = str(src.get("skill") or "").strip().lower() or None
    action = str(src.get("skill_action") or "").strip().lower() or None
    if skill not in SKILLS:
        skill = None
    inferred = HINT_SKILL.get(hint)
    if hint == "tool" and task_type == "media_generation":
        inferred = ("media_file", "generate_media")
    elif hint == "tool" and task_type == "file_processing":
        inferred = ("media_file", "process_file")
    if skill is None and inferred:
        skill, default_action = inferred
        if not action:
            action = default_action
    if skill and not action:
        action = (inferred or (None, "run"))[1] or "run"
    return skill, action


def normalize_tasks(raw: Any, count: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows = raw[:count] if count else raw
    out: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        hint = str(item.get("task_hint") or "").strip().lower()
        if hint not in TASK_HINTS:
            continue
        ttype = str(item.get("task_type") or "").strip().lower()
        if ttype not in TASK_TYPES:
            ttype = HINT_EXECUTION.get(hint, ("interactive", "chat", "ack_then_deliver"))[1]
        out.append({"task_hint": hint, "task_type": ttype})
    return out


def plan_compound_sequential(plan: dict[str, Any] | None) -> bool:
    """True when classify split this bubble into multiple immediate parts (Zalo FIFO order)."""
    src = plan if isinstance(plan, dict) else {}
    if str(src.get("task_hint") or "").strip().lower() == "schedule":
        return False
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    return len(parts) >= 2


def plan_is_async(plan: dict[str, Any] | None) -> bool:
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    for detail in src.get("task_details") or []:
        if not isinstance(detail, dict):
            continue
        if str(detail.get("execution_class") or "").strip().lower() == "async":
            return True
        if str(detail.get("response_mode") or "").strip().lower() == "ack_then_deliver":
            return True
        if str(detail.get("task_type") or "").strip().lower() in {"media_generation", "file_processing"}:
            return True
    if str(src.get("execution_class") or "").strip().lower() == "async":
        return True
    return str(src.get("response_mode") or "").strip().lower() == "ack_then_deliver"


def failed_plan(timezone: str, error: str = "classify_unavailable") -> dict[str, Any]:
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    return {
        "ok": False,
        "task_hint": "unknown",
        "instructions": [],
        "task_details": [],
        "cadence": None,
        "cron_expr": None,
        "timezone": tz,
        "error": error,
        "execution_class": "interactive",
        "task_type": "chat",
        "response_mode": "confirm",
        "process_original_message": False,
        "message": "",
        "attachments_required": False,
        "attachment_types": [],
        "skill": None,
        "skill_action": None,
        "tasks": [],
        "target_channel": None,
    }


def plan_schema_ok(plan: dict[str, Any]) -> bool:
    if not isinstance(plan, dict) or plan.get("ok") is False:
        return False
    if str(plan.get("task_hint") or "") == "schedule" and not plan.get("cron_expr"):
        return False
    return True


def normalize_plan(data: dict[str, Any] | None, text: str, timezone: str) -> dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    if src.get("ok") is False:
        return failed_plan(timezone, str(src.get("error") or "classify_unavailable"))
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint in {"secret", "blocked", "sensitive"}:
        hint = "unknown"
    hint = HINT_ALIASES.get(hint, hint)
    if hint not in TASK_HINTS:
        hint = "unknown"
    fallback = (text or "").strip()
    instructions = sanitize_instructions(src.get("instructions"), fallback)
    cadence = str(src.get("cadence") or "").strip().lower()
    if cadence not in CADENCES:
        cadence = "daily" if hint == "schedule" else "once"
    cron = valid_cron(str(src.get("cron_expr") or ""))
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    exec_cls, task_type, response_mode = normalize_execution(src, hint)
    skill, skill_action = normalize_skill(src, hint, task_type)
    message = str(src.get("message") or "").strip()
    if not message:
        if len(instructions) == 1:
            message = instructions[0]
        elif instructions:
            message = "\n".join(instructions)
        else:
            message = fallback
    process_original = src.get("process_original_message")
    if not isinstance(process_original, bool):
        process_original = hint != "schedule"
    attachments_required = src.get("attachments_required")
    if not isinstance(attachments_required, bool):
        attachments_required = False
    plan = {
        "ok": True,
        "task_hint": hint,
        "instructions": instructions,
        "task_details": normalize_task_details(src, instructions, hint),
        "cadence": cadence if hint == "schedule" else None,
        "cron_expr": cron if hint == "schedule" else None,
        "timezone": tz,
        "execution_class": exec_cls,
        "task_type": task_type,
        "response_mode": response_mode,
        "process_original_message": process_original,
        "message": message,
        "attachments_required": attachments_required,
        "attachment_types": normalize_attachment_types(src.get("attachment_types")),
        "skill": skill,
        "skill_action": skill_action,
        "tasks": normalize_tasks(src.get("tasks"), len(instructions)),
        "target_channel": (
            str(
                src.get("target_channel")
                or src.get("deliver_to")
                or src.get("target_group")
                or src.get("group_name")
                or ""
            ).strip()
            or None
        ),
    }
    if not plan_schema_ok(plan):
        return failed_plan(tz, "classify_invalid")
    return plan


def classify_text(text: str, *, timezone: str = "Asia/Ho_Chi_Minh") -> dict[str, Any]:
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    blob = (text or "").strip()
    if _planner is not None:
        try:
            return normalize_plan(_planner(blob, timezone=tz), blob, tz)
        except TypeError:
            return normalize_plan(_planner(blob), blob, tz)
    if not blob:
        return normalize_plan({"task_hint": "unknown", "instructions": []}, "", tz)
    base = (os.environ.get("MODEL_ROUTER_URL") or "http://model-router:8096").rstrip("/")
    payload = json.dumps({"text": blob, "timezone": tz}, ensure_ascii=False).encode("utf-8")
    timeout = float(os.environ.get("MODEL_ROUTER_CLASSIFY_TIMEOUT_S") or DEFAULT_TIMEOUT_S)
    last_error = "classify_unavailable"
    for _attempt in range(HTTP_ATTEMPTS):
        req = urllib.request.Request(
            base + "/v1/classify",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8") or "{}")
            if isinstance(data, dict) and data.get("ok"):
                plan = normalize_plan(data, blob, tz)
                if plan_schema_ok(plan):
                    return plan
                last_error = "classify_invalid"
                continue
            if isinstance(data, dict) and data.get("ok") is False:
                last_error = str(data.get("error") or "classify_unavailable")
                continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            last_error = "classify_http_error"
            continue
    return failed_plan(tz, last_error)


OUTBOUND_ACTIONS = ("send", "drop")
_outbound_planner: Planner | None = None


def set_outbound_planner(fn: Planner | None) -> None:
    global _outbound_planner
    _outbound_planner = fn


def normalize_outbound(data: dict[str, Any] | None) -> dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    action = str(src.get("action") or "send").strip().lower()
    if action not in OUTBOUND_ACTIONS:
        action = "send"
    if src.get("ok") is False:
        return {
            "ok": False,
            "action": action,
            "error": str(src.get("error") or "outbound_failed"),
        }
    return {"ok": True, "action": action}


def classify_outbound(text: str) -> dict[str, Any]:
    blob = (text or "").strip()
    if not blob:
        return {"ok": True, "action": "drop"}
    if _outbound_planner is not None:
        try:
            return normalize_outbound(_outbound_planner(blob))
        except TypeError:
            return normalize_outbound(_outbound_planner(blob, timezone="Asia/Ho_Chi_Minh"))
    base = (os.environ.get("MODEL_ROUTER_URL") or "http://model-router:8096").rstrip("/")
    payload = json.dumps({"text": blob}, ensure_ascii=False).encode("utf-8")
    timeout = float(os.environ.get("MODEL_ROUTER_OUTBOUND_TIMEOUT_S") or 30.0)
    try:
        req = urllib.request.Request(
            base + "/v1/outbound",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        if isinstance(data, dict):
            return normalize_outbound(data)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        pass
    return {"ok": False, "action": "send", "error": "outbound_unavailable"}
