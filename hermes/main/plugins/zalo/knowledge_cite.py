"""Knowledge-cite intercept consumes LLM classify only.

task_hint=knowledge → catalog/cite via ingest.
Any other hint (including schedule) reaches workflow/Hermes.
Classify failure must not cite-bypass Hermes (rule 15 / 36).
"""
from __future__ import annotations

from typing import Any


def plan_is_knowledge(plan: dict[str, Any] | None) -> bool:
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    return str(src.get("task_hint") or "").strip().lower() == "knowledge"


def cite_query(plan: dict[str, Any] | None) -> str:
    src = plan if isinstance(plan, dict) else {}
    items = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    return items[0] if items else ""
