"""Drop Hermes gateway UX that must never reach Zalo users."""
from __future__ import annotations

BUSY_INTERRUPT_NEEDLES = (
    "interrupting current task",
    "i'll respond to your message shortly",
    "i will respond to your message shortly",
    "first-time tip",
    "/busy queue",
    "/busy steer",
    "/busy status",
    "send `/busy",
    "send /busy",
    "this notice won't appear again",
    "redirected current run",
    "your current task will be interrupted",
)


def is_busy_interrupt_notice(content: str) -> bool:
    """True when Hermes injected a busy/interrupt / /busy tip."""
    low = (content or "").strip().lower()
    if not low:
        return False
    return any(n in low for n in BUSY_INTERRUPT_NEEDLES)
