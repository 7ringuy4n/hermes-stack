# -*- coding: utf-8 -*-
"""Unit: scheduled search-then-note fire coerces plan + fire_text fallback."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from notes_persist import (  # noqa: E402
    coerce_schedule_fire_plan_for_search_note,
    should_defer_note_persist,
    strip_schedule_timing_prefix,
    text_wants_search_then_note,
)
from schedule_client import fire_text_from_plan  # noqa: E402


ASK = (
    "5 phút nữa truy cập các nhóm public facebook, các kênh ITviec, TopCV, topDev, "
    "etc... tìm cho tôi các tin chi tiết các tin tuyển dụng fullstack, BE Java ở "
    "hồ chí minh còn hiệu lực và gần nhất và ghi chú lại"
)


def main() -> int:
    print("running test case 1/7")
    assert text_wants_search_then_note(ASK)
    assert "facebook" in strip_schedule_timing_prefix(ASK).lower()
    assert strip_schedule_timing_prefix(ASK).lower().startswith("truy cập") or strip_schedule_timing_prefix(
        ASK
    ).lower().startswith("truy cap") or "tìm" in strip_schedule_timing_prefix(ASK).lower() or "tim" in strip_schedule_timing_prefix(
        ASK
    ).lower()

    print("running test case 2/7")
    sched_plan = {
        "ok": True,
        "task_hint": "schedule",
        "schedule_form": "once_after",
        "delay_seconds": 300,
        "instructions": [ASK],  # bad classify: full ask
        "message": ASK,
    }
    # Deferred persist must arm for schedule + search-then-note wording.
    assert should_defer_note_persist(sched_plan, ASK)

    print("running test case 3/7")
    coerced = coerce_schedule_fire_plan_for_search_note(sched_plan, ASK)
    assert coerced["task_hint"] == "search"
    assert coerced.get("process_original_message") is True
    assert should_defer_note_persist(coerced, ASK)

    print("running test case 4/7")
    # fire_text must not be empty when instructions == full ask.
    fire = fire_text_from_plan(sched_plan, ASK)
    assert fire, fire
    assert fire != ASK
    assert "tìm" in fire.lower() or "tim" in fire.lower() or "facebook" in fire.lower()

    print("running test case 5/7")
    good = {
        "ok": True,
        "task_hint": "schedule",
        "instructions": [
            "Search ITviec/TopCV/TopDev/Facebook for current Java fullstack BE jobs in HCM then note them"
        ],
        "message": "Search ITviec/TopCV for Java fullstack HCM jobs then note them",
    }
    fire2 = fire_text_from_plan(good, ASK)
    assert "Search ITviec" in fire2 or "Java" in fire2

    print("running test case 6/7")
    adapter = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    assert "coerce_schedule_fire_plan_for_search_note" in adapter
    assert "Current lookup execution contract" in adapter

    print("running test case 7/7")
    # Unrelated schedule reminder must not be coerced into search.
    reminder = {
        "ok": True,
        "task_hint": "schedule",
        "instructions": ["Remind me to drink water"],
        "message": "Remind me to drink water",
    }
    rem_ask = "5 phút nữa nhắc tôi uống nước"
    out = coerce_schedule_fire_plan_for_search_note(reminder, rem_ask)
    assert out.get("task_hint") == "schedule"

    print("schedule_search_note_fire_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
