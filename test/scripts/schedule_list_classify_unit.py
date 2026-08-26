# -*- coding: utf-8 -*-
"""list_schedule vs delete_schedule normalize + schema."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify import normalize_plan, plan_schema_ok  # noqa: E402
from schedule_client import format_schedule_list_lines  # noqa: E402


def main() -> int:
    listed = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "list_schedule",
            "skill": "schedule",
            "skill_action": "list",
            "instructions": ["liệt kê lịch nhắc"],
            "process_original_message": False,
        },
        "lịch nhắc này của tôi đâu?",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(listed), listed
    assert listed.get("task_type") == "list_schedule", listed
    assert listed.get("skill_action") == "list", listed
    assert listed.get("cron_expr") in (None, ""), listed
    assert listed.get("schedule_delivery") in (None, ""), listed

    # Quote hydrate must still normalize as list when model emits list fields.
    quoted = normalize_plan(
        {
            "task_hint": "schedule",
            "skill_action": "list",
            "task_type": "list_schedule",
            "instructions": ["xem lịch"],
        },
        "[Quoted message]\n1 phút nữa nhắn tôi nội dung: hello\n\nlịch nhắc này của tôi đâu?",
        "Asia/Ho_Chi_Minh",
    )
    assert quoted.get("skill_action") == "list", quoted
    assert quoted.get("task_type") == "list_schedule", quoted

    deleted = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "delete_schedule",
            "skill_action": "delete",
            "instructions": ["xóa lịch số 1"],
        },
        "xóa lịch số 1",
        "Asia/Ho_Chi_Minh",
    )
    assert deleted.get("skill_action") == "delete", deleted
    assert plan_schema_ok(deleted)

    paused = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "pause_schedule",
            "skill_action": "pause",
            "schedule_selector": {"id": "x", "name": "fuel", "match": {"content_hint": "xăng"}},
            "instructions": ["tạm dừng"],
        },
        "tạm dừng lịch xăng",
        "Asia/Ho_Chi_Minh",
    )
    assert paused.get("task_type") == "pause_schedule", paused
    assert paused.get("skill_action") == "pause", paused
    assert (paused.get("schedule_selector") or {}).get("id") is None
    assert plan_schema_ok(paused)

    assert "Chưa có lịch" in format_schedule_list_lines([])
    assert "sch_1" in format_schedule_list_lines(
        [{"id": "sch_1", "next_run_at": "2026-08-25T14:00:00Z", "origin": {"target_name": "LC group"}}]
    )
    print("OK schedule list vs delete normalize")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
