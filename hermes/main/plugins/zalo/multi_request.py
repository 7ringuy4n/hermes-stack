"""Zalo compound + schedule splitting via LLM classify. No regex NLU for intent.

Immediate multi-request bubbles: classify emits N instructions; the host runs them
sequentially (one turn at a time). Schedule: one fire payload or one job per
classify tasks[] entry.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List

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


def split_compound_requests(text: str) -> List[str]:
    raw = strip_prior_for_classify(text or "")
    if not raw:
        return []
    plan = classify_text(raw)
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
    return items or [raw]


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
