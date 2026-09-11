# -*- coding: utf-8 -*-
"""Unit: scheduled search-then-note fire coerces from classify plan flag."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from notes_persist import (  # noqa: E402
    coerce_schedule_fire_plan_for_search_note,
    should_defer_note_persist,
)
from schedule_client import fire_text_from_plan  # noqa: E402


INNER = (
    "Search public Facebook groups, ITviec, TopCV, TopDev for current Java "
    "fullstack BE openings in HCM and note the concrete findings"
)


def main() -> int:
    print("running test case 1/6")
    sched_plan = {
        "ok": True,
        "task_hint": "schedule",
        "schedule_form": "once_after",
        "delay_seconds": 300,
        "persist_gathered_notes": True,
        "instructions": [INNER],
        "message": INNER,
    }
    assert should_defer_note_persist(sched_plan)

    print("running test case 2/6")
    coerced = coerce_schedule_fire_plan_for_search_note(sched_plan)
    assert coerced["task_hint"] == "search"
    assert coerced.get("process_original_message") is True
    assert coerced.get("persist_gathered_notes") is True
    assert should_defer_note_persist(coerced)

    print("running test case 3/6")
    fire = fire_text_from_plan(sched_plan, "5 phút nữa " + INNER)
    assert fire, fire
    assert "Java" in fire or "ITviec" in fire

    print("running test case 4/6")
    # Without classify flag, schedule reminder must not coerce to search.
    reminder = {
        "ok": True,
        "task_hint": "schedule",
        "instructions": ["Remind me to drink water"],
        "message": "Remind me to drink water",
    }
    out = coerce_schedule_fire_plan_for_search_note(reminder, "5 phút nữa nhắc tôi uống nước")
    assert out.get("task_hint") == "schedule"

    print("running test case 5/6")
    assert not should_defer_note_persist(
        {"task_hint": "schedule", "instructions": [INNER]},
        INNER,
    )

    print("running test case 6/6")
    adapter = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    assert "coerce_schedule_fire_plan_for_search_note" in adapter
    assert "load_search_then_note_contract" in adapter
    skill = (ROOT / "hermes" / "main" / "skills" / "classify" / "parts" / "notes.txt").read_text(
        encoding="utf-8"
    )
    assert "persist_gathered_notes true" in skill

    print("schedule_search_note_fire_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
