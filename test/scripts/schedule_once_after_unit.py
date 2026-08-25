# -*- coding: utf-8 -*-
"""once_after delay_seconds + host timing resolution (no LLM clock)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify import (  # noqa: E402
    delay_seconds_from_text,
    normalize_plan,
    plan_schema_ok,
    schedule_heuristic_plan,
)
from schedule_client import (  # noqa: E402
    resolve_schedule_timing,
)
from classify_client import (  # noqa: E402
    plan_allows_office_shortcut,
    plan_is_immediate_deliver,
    plan_skips_media_shortcut,
)


def main() -> int:
    rel = "1 phút nữa gửi vào Zalo LC Group: em muốn hầu hạ Boss Hải"
    assert delay_seconds_from_text(rel) == 60, delay_seconds_from_text(rel)
    raw = schedule_heuristic_plan(rel)
    assert raw and raw.get("schedule_form") == "once_after", raw
    assert raw.get("delay_seconds") == 60, raw
    assert raw.get("cron_expr") in (None, ""), raw
    plan = normalize_plan(raw, rel, "Asia/Ho_Chi_Minh")
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
    assert timing["next_run_at"].endswith("Z")
    assert "17" not in (timing["next_run_at"] or "")

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

    once = normalize_plan(
        {
            "task_hint": "schedule",
            "schedule_form": "once_at",
            "cron_expr": "31 17 * * *",
            "cadence": "once",
            "instructions": ["hello"],
            "process_original_message": False,
        },
        "đặt lịch lúc 09:50 với nội dung hello",
        "Asia/Ho_Chi_Minh",
    )
    assert once.get("schedule_form") == "once_at", once
    assert once.get("cron_expr") == "50 9 * * *", once
    assert plan_schema_ok(once)

    print("OK once_after + media compound guards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
