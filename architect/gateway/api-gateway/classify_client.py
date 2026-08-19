"""HTTP client for model-router POST /v1/classify.

Application code consumes structured JSON only. Tests may inject set_planner.
Keep in sync with workflow and Zalo copies.
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
HINT_EXECUTION = {
    "schedule": ("schedule", "create_schedule", "confirm"),
    "file": ("async", "file_processing", "ack_then_deliver"),
    "knowledge": ("interactive", "knowledge", "direct"),
    "coding": ("interactive", "coding", "direct"),
    "search": ("interactive", "search", "direct"),
    "normal": ("interactive", "chat", "direct"),
    "unknown": ("interactive", "chat", "direct"),
    "tool": ("interactive", "tool", "direct"),
}
CRON_CHARS = set("0123456789*,/-")
DEFAULT_TIMEOUT_S = 8.0
HTTP_ATTEMPTS = 1


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


def normalize_execution(src: dict[str, Any], hint: str) -> tuple[str, str, str]:
    raw_cls = str(src.get("execution_class") or "").strip().lower()
    raw_type = str(src.get("task_type") or "").strip().lower()
    raw_mode = str(src.get("response_mode") or "").strip().lower()
    d_cls, d_type, d_mode = HINT_EXECUTION.get(hint, ("interactive", "chat", "direct"))
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
    if hint == "schedule":
        return "schedule", "create_schedule", "confirm"
    return raw_cls, raw_type, raw_mode


def plan_is_async(plan: dict[str, Any] | None) -> bool:
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    if str(src.get("execution_class") or "").strip().lower() == "async":
        return True
    return str(src.get("response_mode") or "").strip().lower() == "ack_then_deliver"


def failed_plan(timezone: str, error: str = "classify_unavailable") -> dict[str, Any]:
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    return {
        "ok": False,
        "task_hint": "unknown",
        "instructions": [],
        "cadence": None,
        "cron_expr": None,
        "timezone": tz,
        "error": error,
        "execution_class": "interactive",
        "task_type": "chat",
        "response_mode": "direct",
    }


def normalize_plan(data: dict[str, Any] | None, text: str, timezone: str) -> dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    if src.get("ok") is False:
        return failed_plan(timezone, str(src.get("error") or "classify_unavailable"))
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint in {"secret", "blocked", "sensitive"}:
        hint = "unknown"
    if hint not in TASK_HINTS:
        hint = "unknown"
    instructions: list[str] = []
    raw_inst = src.get("instructions")
    if isinstance(raw_inst, list):
        for item in raw_inst:
            s = str(item).strip()
            if s:
                instructions.append(s)
    fallback = (text or "").strip()
    if not instructions and fallback:
        instructions = [fallback]
    cadence = str(src.get("cadence") or "").strip().lower()
    if cadence not in CADENCES:
        cadence = "daily" if hint == "schedule" else "once"
    cron = valid_cron(str(src.get("cron_expr") or ""))
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    exec_cls, task_type, response_mode = normalize_execution(src, hint)
    return {
        "ok": True,
        "task_hint": hint,
        "instructions": instructions,
        "cadence": cadence if hint == "schedule" else None,
        "cron_expr": cron if hint == "schedule" else None,
        "timezone": tz,
        "execution_class": exec_cls,
        "task_type": task_type,
        "response_mode": response_mode,
    }


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
                return normalize_plan(data, blob, tz)
            if isinstance(data, dict) and data.get("ok") is False:
                last_error = str(data.get("error") or "classify_unavailable")
                continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            last_error = "classify_http_error"
            continue
    return failed_plan(tz, last_error)
