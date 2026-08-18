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

PROCESS_NARRATION_NEEDLES = (
    "now i have the",
    "now i need to",
    "let me analyze",
    "let me fetch",
    "let me get a python",
    "let me overlay",
    "python environment with pil",
    "phiên làm việc đã được khôi phục",
    "session has been restored",
    "session restored successfully",
    "bạn có muốn tôi gửi lại",
    "mình đang lấy",
    "let me extract image",
)


def is_busy_interrupt_notice(content: str) -> bool:
    """True when Hermes injected a busy/interrupt / /busy tip."""
    low = (content or "").strip().lower()
    if not low:
        return False
    return any(n in low for n in BUSY_INTERRUPT_NEEDLES)


def is_process_narration(content: str) -> bool:
    """True when the model is narrating search/OCR/image steps."""
    low = (content or "").strip().lower()
    if not low:
        return False
    return any(n in low for n in PROCESS_NARRATION_NEEDLES)
