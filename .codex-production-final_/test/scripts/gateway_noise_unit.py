# -*- coding: utf-8 -*-
"""Unit tests for Zalo outbound drop (LLM classify, injected planner)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify_client import set_outbound_planner  # noqa: E402
from gateway_noise import drop_outbound, is_busy_interrupt_notice, is_process_narration  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BUSY = (
    "⚡ Interrupting current task. I'll respond to your message shortly.\n"
    "💡 First-time tip — I just interrupted my current task to answer you. "
    "Send `/busy queue` to queue follow-ups for after the current task instead, "
    "`/busy steer` to inject them mid-run without interrupting, or `/busy status` to check. "
    "This notice won't appear again."
)


def _planner(text: str, timezone: str = "Asia/Ho_Chi_Minh") -> dict:
    low = (text or "").strip().lower()
    drop = (
        "interrupting current task" in low
        or "/busy" in low
        or "now i have the page" in low
        or "phiên làm việc đã được khôi phục" in low
        or "manim" in low
        or "pangocairo" in low
        or "rendering frames" in low
    )
    return {"action": "drop" if drop else "send"}


def main() -> int:
    set_outbound_planner(_planner)
    if not is_busy_interrupt_notice(BUSY):
        print("FAIL expected busy interrupt notice to be dropped")
        return 1
    if not is_busy_interrupt_notice("Interrupting current task. I'll respond shortly."):
        print("FAIL short interrupt line")
        return 1
    if is_busy_interrupt_notice("Đã xong."):
        print("FAIL result line must not be noise")
        return 1
    if is_busy_interrupt_notice("Giá xăng E5 RON92"):
        print("FAIL fuel reply must not be noise")
        return 1
    if not is_process_narration("Now I have the page with the two fuel price images."):
        print("FAIL process narration must drop")
        return 1
    if not is_process_narration("Phiên làm việc đã được khôi phục thành công."):
        print("FAIL session restored must drop")
        return 1
    if not is_process_narration("Manim can't be installed (missing system dependency pangocairo)."):
        print("FAIL manim install chatter must drop")
        return 1
    if not is_process_narration("Rendering frames..."):
        print("FAIL rendering frames must drop")
        return 1
    if not drop_outbound("✓ Context compaction complete — continuing turn..."):
        print("FAIL compaction protocol must drop")
        return 1
    if not drop_outbound("⚠️ Request payload too large (413) — compression attempt 1/3..."):
        print("FAIL 413 protocol must drop")
        return 1
    if not drop_outbound(
        "🔄 Session auto-reset — the conversation exceeded the maximum context size "
        "and could not be compressed further. Your next message will start a fresh session."
    ):
        print("FAIL session auto-reset protocol must drop")
        return 1
    if not drop_outbound(
        "⚠️ Cron 'Báo cáo' failed: vars() argument must have __dict__ attribute"
    ):
        print("FAIL python exception protocol must drop")
        return 1
    set_outbound_planner(None)
    import gateway_noise as gn  # noqa: E402

    def _fail(_t: str) -> dict:
        return {"ok": False, "action": "drop", "error": "outbound_unavailable"}

    _orig = gn.classify_outbound
    gn.classify_outbound = _fail
    try:
        if drop_outbound("Chúc bạn một buổi sáng tốt lành!"):
            print("FAIL greeting must send when outbound classify unavailable")
            return 1
    finally:
        gn.classify_outbound = _orig
    set_outbound_planner(_planner)
    if drop_outbound(""):
        pass
    else:
        print("FAIL empty line must drop")
        return 1
    print("PASS busy interrupt dropped; user results kept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
