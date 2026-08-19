"""Zalo uses LLM classify for multi-task / schedule intent. No regex NLU."""
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
