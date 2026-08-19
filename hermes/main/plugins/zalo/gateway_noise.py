"""Drop Hermes outbound that must not reach Zalo users.

Application code consumes LLM outbound classify (`action=send|drop`).
Tests inject set_outbound_planner. Empty lines are not sent.
"""
from __future__ import annotations

from classify_client import classify_outbound


def drop_outbound(content: str) -> bool:
    t = (content or "").strip()
    if not t:
        return True
    return str(classify_outbound(t).get("action") or "send").strip().lower() == "drop"


def is_busy_interrupt_notice(content: str) -> bool:
    return drop_outbound(content)


def is_process_narration(content: str) -> bool:
    return drop_outbound(content)
