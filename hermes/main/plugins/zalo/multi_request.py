"""Zalo compound + schedule splitting via LLM classify. No regex NLU for intent.

Immediate multi-request bubbles: classify emits N instructions; the host runs them
sequentially (one turn at a time). Schedule: one fire payload or one job per
classify tasks[] entry.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_d = Path(__file__).resolve().parent
_shared = Path(os.getenv("HERMES_SHARED_DATA") or "/opt/data") / "plugins" / "zalo"
for _p in (_d, _shared):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

from classify_client import classify_text, strip_prior_for_classify


def looks_like_schedule_job(text: str) -> bool:
    plan = classify_text(text or "")
    return plan.get("task_hint") == "schedule"


def parts_from_plan(raw: str, plan: Dict[str, Any]) -> List[str]:
    """Return independent user jobs without splitting one dependency graph."""
    try:
        from .notes_persist import keep_search_then_note_atomic
    except ImportError:
        from notes_persist import keep_search_then_note_atomic  # type: ignore
    # Search-then-note must stay one gather + one host persist (no FIFO split).
    if keep_search_then_note_atomic(plan if isinstance(plan, dict) else {}, raw):
        return [raw]
    tasks = plan.get("tasks") or []
    if isinstance(tasks, list) and len(tasks) >= 2:
        out: List[str] = []
        for item in tasks:
            if not isinstance(item, dict):
                continue
            ins = [str(x).strip() for x in (item.get("instructions") or []) if str(x).strip()]
            if ins:
                out.append("\n".join(ins))
        if len(out) >= 2:
            return out
    items = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
    if plan.get("task_hint") == "schedule":
        return [raw]
    details = plan.get("task_details") or []
    if isinstance(details, list) and len(details) == len(items):
        for item in details:
            if isinstance(item, dict) and item.get("depends_on"):
                return [raw]
    return items or [raw]


def classify_compound_request(text: str) -> Tuple[List[str], Dict[str, Any]]:
    """Classify once and return both independent parts and the reusable plan."""
    raw = strip_prior_for_classify(text or "")
    if not raw:
        return [], {}
    plan = classify_text(raw)
    return parts_from_plan(raw, plan), plan


def queue_part_text(raw: str, parts: List[str]) -> str:
    """Preserve an atomic user's wording; use planned text only for real splits."""
    values = [str(value or "").strip() for value in parts if str(value or "").strip()]
    if len(values) >= 2:
        return values[0]
    return str(raw or "")


def split_compound_requests(text: str) -> List[str]:
    parts, _plan = classify_compound_request(text)
    return parts


def wrap_compound_part(index: int, total: int, body: str) -> str:
    text = (body or "").strip()
    if not text:
        return text
    return (
        f"Yêu cầu {index}/{total} — chỉ làm đúng việc này, rồi dừng. "
        f"Không làm các mục khác.\n"
        f"{text}"
    )


def plan_instructions(text: str) -> List[str]:
    raw = strip_prior_for_classify(text or "")
    if not raw:
        return []
    plan = classify_text(raw)
    items = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
    return items or [raw]
