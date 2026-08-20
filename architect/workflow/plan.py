"""Job instruction helpers. Classification is LLM-owned (classify_client).

This module only validates cron tokens, cadence enums, and wraps already-split
instructions for isolated job execution.
"""
from __future__ import annotations

from typing import Any, List, Optional

from classify_client import CADENCES, classify_text, valid_cron

CADENCE_ONCE = "once"
CADENCE_DAILY = "daily"
CADENCE_WEEKLY = "weekly"
CADENCE_MONTHLY = "monthly"
CADENCE_YEARLY = "yearly"


def wrap_instruction(index: int, total: int, body: str) -> str:
    text = (body or "").strip()
    if total <= 1:
        return text
    return (
        f"Yêu cầu {index}/{total} — chỉ làm đúng việc này, rồi dừng. "
        f"Không làm các mục khác.\n{text}"
    )


def resolve_cadence(raw: str, text: str = "") -> str:
    kind = (raw or "").strip().lower()
    if kind in CADENCES:
        return kind
    if (text or "").strip():
        plan = classify_text(text)
        cadence = str(plan.get("cadence") or "").strip().lower()
        if cadence in CADENCES:
            return cadence
    return CADENCE_ONCE


def extract_cadence(text: str) -> str:
    return resolve_cadence("", text)


def extract_cron_expr(text: str) -> Optional[str]:
    """Accept a 5-field cron token string, or ask the LLM for one from prose."""
    direct = valid_cron(text or "")
    if direct:
        return direct
    if not (text or "").strip():
        return None
    plan = classify_text(text)
    return valid_cron(str(plan.get("cron_expr") or ""))


def plan_instructions(text: str) -> List[str]:
    """Instructions from LLM classify. Fallback: the original text as one job."""
    raw = (text or "").strip()
    if not raw:
        return []
    plan = classify_text(raw)
    items = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
    return items or [raw]


def plan_graph_from_stored(sch: dict[str, Any], text: str) -> tuple[List[str], List[dict[str, Any]]]:
    ctx = sch.get("context") if isinstance(sch.get("context"), dict) else {}
    stored = ctx.get("plan") if isinstance(ctx.get("plan"), dict) else {}
    stored_items = [str(x).strip() for x in (stored.get("instructions") or []) if str(x).strip()]
    live = classify_text((text or "").strip()) if (text or "").strip() else {}
    live_items = [str(x).strip() for x in (live.get("instructions") or []) if str(x).strip()]
    live_details = live.get("task_details") if isinstance(live.get("task_details"), list) else []
    stored_details = stored.get("task_details") if isinstance(stored.get("task_details"), list) else []
    if len(live_items) > len(stored_items):
        return live_items, [d for d in live_details if isinstance(d, dict)]
    if stored_items:
        return stored_items, [d for d in stored_details if isinstance(d, dict)]
    if live_items:
        return live_items, [d for d in live_details if isinstance(d, dict)]
    fallback = [(text or "").strip()] if (text or "").strip() else []
    return fallback, []


def plan_from_stored(sch: dict[str, Any], text: str) -> List[str]:
    parts, _details = plan_graph_from_stored(sch, text)
    return parts
