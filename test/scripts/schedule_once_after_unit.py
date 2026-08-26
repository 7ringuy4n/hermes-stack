# -*- coding: utf-8 -*-
"""once_after delay_seconds + host timing resolution (no classify regex)."""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify import (  # noqa: E402
    heuristic_plan,
    normalize_plan,
    plan_schema_ok,
)
from schedule_client import (  # noqa: E402
    independent_schedule_plans,
    next_run_at_from_delay,
    resolve_schedule_timing,
)
from classify_client import (  # noqa: E402
    plan_allows_office_shortcut,
    plan_is_immediate_deliver,
    plan_skips_media_shortcut,
)


def main() -> int:
    rel = "1 phút nữa gửi vào Zalo LC Group: em muốn hầu hạ Boss Hải"
    assert heuristic_plan(rel) is None
    plan = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill_action": "create",
            "schedule_form": "once_after",
            "delay_seconds": 60,
            "cron_expr": None,
            "cadence": "once",
            "instructions": ["em muốn hầu hạ Boss Hải"],
            "target_channel": "LC group",
            "process_original_message": False,
        },
        rel,
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(plan), plan
    assert plan.get("delay_seconds") == 60, plan
    assert plan.get("cron_expr") in (None, ""), plan
    assert plan.get("next_run_at") in (None, ""), plan

    poisoned = normalize_plan(
        {
            "task_hint": "schedule",
            "schedule_form": "once_after",
            "delay_seconds": 60,
            "cron_expr": "31 17 * * *",
            "next_run_at": "2026-08-25T10:31:00Z",
            "cadence": "once",
            "instructions": ["em muốn hầu hạ Boss Hải"],
            "target_channel": "LC group",
            "process_original_message": False,
        },
        rel,
        "Asia/Ho_Chi_Minh",
    )
    assert poisoned.get("cron_expr") in (None, ""), poisoned
    assert poisoned.get("next_run_at") in (None, ""), poisoned
    timing = resolve_schedule_timing(poisoned, rel, "Asia/Ho_Chi_Minh")
    assert timing["schedule_form"] == "once_after"
    assert timing["delay_seconds"] == 60
    nxt = timing["next_run_at"]
    assert nxt.endswith("Z"), timing
    assert "T17:31:" not in nxt, timing
    parsed = datetime.datetime.strptime(nxt, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc
    )
    skew = abs((parsed - datetime.datetime.now(datetime.timezone.utc)).total_seconds() - 60)
    assert skew < 5, timing

    receipt = datetime.datetime(2026, 8, 26, 4, 0, 0, tzinfo=datetime.timezone.utc)
    stamped = next_run_at_from_delay(90, received_at=receipt)
    assert stamped == "2026-08-26T04:01:30Z", stamped
    late = resolve_schedule_timing(
        poisoned,
        rel,
        "Asia/Ho_Chi_Minh",
        received_at=receipt,
    )
    assert late["next_run_at"] == "2026-08-26T04:01:00Z", late

    jobs = independent_schedule_plans(
        {
            "task_hint": "schedule",
            "delay_seconds": None,
            "tasks": [
                {"task_hint": "schedule", "delay_seconds": 60, "instructions": ["a"]},
                {"task_hint": "schedule", "delay_seconds": 90, "instructions": ["b"]},
                {"task_hint": "schedule", "delay_seconds": 120, "instructions": ["c"]},
            ],
        }
    )
    assert len(jobs) == 3, jobs
    assert [j.get("delay_seconds") for j in jobs] == [60, 90, 120]

    missing = resolve_schedule_timing(
        {"task_hint": "schedule", "schedule_form": "once_after", "delay_seconds": None},
        rel,
        "Asia/Ho_Chi_Minh",
    )
    assert not missing.get("next_run_at"), missing

    mixed = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "instructions": ["vẽ hình chào buổi sáng", "tạo file text đã xong"],
        "task_details": [
            {"task_type": "media_generation", "output_type": "image"},
            {"task_type": "file_processing", "output_type": "txt"},
        ],
    }
    assert plan_skips_media_shortcut(mixed) is True
    assert plan_allows_office_shortcut(mixed) is False
    assert plan_is_immediate_deliver(
        {"ok": True, "task_hint": "normal", "skill_action": "deliver", "target_channel": "LC group"}
    )
    assert plan_is_immediate_deliver({"ok": True, "task_hint": "schedule", "skill_action": "create"}) is False

    compound = {
        "ok": True,
        "task_hint": "tool",
        "instructions": [
            "vẽ 1 tấm hình trắng đen ghi vào chào buổi sáng",
            "tạo 1 file text ghi vào đã xong",
        ],
    }
    assert plan_skips_media_shortcut(compound) is True
    assert plan_allows_office_shortcut(compound) is False
    assert plan_skips_media_shortcut(
        {"ok": True, "task_hint": "schedule", "instructions": ["hello"]}
    ) is True

    once_text = "đặt lịch lúc 09:50 với nội dung hello"
    once = normalize_plan(
        {
            "task_hint": "schedule",
            "schedule_form": "once_at",
            "clock_hm": "09:50",
            "cron_expr": "31 17 * * *",
            "cadence": "once",
            "instructions": ["hello"],
            "process_original_message": False,
        },
        once_text,
        "Asia/Ho_Chi_Minh",
    )
    assert once.get("schedule_form") == "once_at", once
    assert once.get("cron_expr") in (None, ""), once
    assert once.get("clock_hm") == "09:50", once
    assert plan_schema_ok(once)
    stored = resolve_schedule_timing(once, once_text, "Asia/Ho_Chi_Minh")
    assert stored.get("cron_expr") == "50 9 * * *", stored
    no_field = normalize_plan(
        {
            "task_hint": "schedule",
            "schedule_form": "once_at",
            "instructions": ["hello"],
            "process_original_message": False,
        },
        once_text,
        "Asia/Ho_Chi_Minh",
    )
    assert not resolve_schedule_timing(no_field, once_text, "Asia/Ho_Chi_Minh").get("cron_expr")

    print("OK once_after JSON delay + host clock protocol + media compound guards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
