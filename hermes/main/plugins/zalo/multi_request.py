"""Zalo uses LLM classify for multi-task / schedule intent. No regex NLU."""
from __future__ import annotations

from typing import List

from classify_client import classify_text


def looks_like_schedule_job(text: str) -> bool:
    plan = classify_text(text or "")
    return plan.get("task_hint") == "schedule"


def split_compound_requests(text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    plan = classify_text(raw)
    if plan.get("task_hint") == "schedule":
        return [raw]
    items = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
    return items or [raw]


def wrap_compound_part(index: int, total: int, body: str) -> str:
    text = (body or "").strip()
    if not text:
        return text
    return (
        f"Yêu cầu {index}/{total} — chỉ làm đúng việc này, rồi dừng. "
        f"Không làm các mục khác.\n{text}"
    )


def plan_instructions(text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    plan = classify_text(raw)
    items = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
    return items or [raw]
