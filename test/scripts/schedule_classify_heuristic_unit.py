# -*- coding: utf-8 -*-
"""Classify skip HTTP + prior strip; LLM JSON is schedule intent SoT (no regex)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))
sys.path.insert(0, str(ROOT / "test" / "scripts"))

from classify import (  # noqa: E402
    _CLASSIFY_SKIP_HTTP,
    _classify_body_is_schema_dead,
    heuristic_plan,
    normalize_plan,
    plan_schema_ok,
    strip_prior_for_classify,
)
from classify_fixtures import (  # noqa: E402
    FIXTURE_EN4,
    FIXTURE_INFOGRAPHIC_DAILY,
    FIXTURE_INFOGRAPHIC_VI,
    FIXTURE_DAILY_LC_TASK,
    _planner,
)


def main() -> int:
    assert 400 in _CLASSIFY_SKIP_HTTP and 503 in _CLASSIFY_SKIP_HTTP
    assert _classify_body_is_schema_dead(
        400,
        '{"errors":[{"message":"AiError: Bad input: required properties at \'/\' are \'prompt\'"}]}',
    )
    wrapped = (
        "[Prior conversation]\nUser: tạo pdf\n[/Prior conversation]\n\n"
        "đặt lịch chạy một lần lúc 20:17 với nội dung chúc mọi người buổi tối"
    )
    bare = strip_prior_for_classify(wrapped)
    assert "[Prior conversation]" not in bare
    assert "đặt lịch" in bare
    # Classify Python must not phrase-scan schedule/destination/delay.
    assert heuristic_plan(bare) is None
    once_llm = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill_action": "create",
            "schedule_form": "once_at",
            "cadence": "once",
            "instructions": ["chúc mọi người buổi tối"],
            "schedule_delivery": "verbatim",
            "process_original_message": False,
        },
        bare,
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(once_llm)
    assert once_llm.get("schedule_form") == "once_at"
    assert once_llm.get("cron_expr") in (None, "")

    en4 = normalize_plan(_planner(FIXTURE_EN4), FIXTURE_EN4, "Asia/Ho_Chi_Minh")
    assert en4["task_hint"] == "tool" and len(en4["instructions"]) == 4, en4
    assert heuristic_plan(FIXTURE_EN4) is None
    assert heuristic_plan(FIXTURE_INFOGRAPHIC_VI) is None
    assert heuristic_plan(FIXTURE_INFOGRAPHIC_DAILY) is None
    daily = normalize_plan(
        _planner(FIXTURE_INFOGRAPHIC_DAILY), FIXTURE_INFOGRAPHIC_DAILY, "Asia/Ho_Chi_Minh"
    )
    assert daily["task_hint"] == "schedule" and daily["cron_expr"] == "0 7 * * *", daily

    daily_lc = FIXTURE_DAILY_LC_TASK
    assert heuristic_plan(daily_lc) is None
    plan_lc = normalize_plan(_planner(daily_lc), daily_lc, "Asia/Ho_Chi_Minh")
    assert plan_schema_ok(plan_lc)
    assert plan_lc.get("schedule_delivery") == "process"
    assert (plan_lc.get("target_channel") or "").lower() == "lc group"
    assert plan_lc.get("cron_expr") == "0 6 * * *"
    assert len(plan_lc.get("instructions") or []) >= 1

    rel = "1 phút nữa gửi vào Zalo LC Group: chào buổi sáng"
    assert heuristic_plan(rel) is None
    plan_rel = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill_action": "create",
            "schedule_form": "once_after",
            "delay_seconds": 60,
            "target_channel": "LC group",
            "schedule_delivery": "process",
            "instructions": ["chào buổi sáng"],
            "process_original_message": False,
        },
        rel,
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(plan_rel)
    assert plan_rel.get("delay_seconds") == 60
    assert not plan_rel.get("cron_expr")
    assert (plan_rel.get("target_channel") or "").lower() == "lc group"

    send_me = (
        "1 phút nữa nhắn tôi nội dung: không cần chit chat, "
        "chỉ mô tả sự cô đơn trong im lặng"
    )
    assert heuristic_plan(send_me) is None
    plan_send = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill_action": "create",
            "schedule_form": "once_after",
            "delay_seconds": 60,
            "schedule_delivery": "verbatim",
            "message": "không cần chit chat, chỉ mô tả sự cô đơn trong im lặng",
            "instructions": ["không cần chit chat, chỉ mô tả sự cô đơn trong im lặng"],
            "process_original_message": False,
        },
        send_me,
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(plan_send)
    assert plan_send.get("schedule_delivery") == "verbatim"
    assert len(plan_send.get("instructions") or []) == 1

    group_desc = (
        "1 phút nữa gửi vào Zalo LC Group mô tả sự cô đơn khi không ai biết đến trợ lý"
    )
    assert heuristic_plan(group_desc) is None
    plan_gd = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill_action": "create",
            "schedule_form": "once_after",
            "delay_seconds": 60,
            "schedule_delivery": "process",
            "target_channel": "LC group",
            "instructions": ["mô tả sự cô đơn khi không ai biết đến trợ lý"],
            "process_original_message": False,
        },
        group_desc,
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(plan_gd)
    assert plan_gd.get("schedule_delivery") == "process"
    assert (plan_gd.get("target_channel") or "").lower() == "lc group"

    wrapper_tasks = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill_action": "create",
            "instructions": ["inner"],
            "tasks": [
                {
                    "task_hint": "schedule",
                    "schedule_form": "once_after",
                    "delay_seconds": 60,
                    "instructions": ["a"],
                },
                {
                    "task_hint": "schedule",
                    "schedule_form": "once_after",
                    "delay_seconds": 90,
                    "instructions": ["b"],
                },
                {
                    "task_hint": "schedule",
                    "schedule_form": "once_after",
                    "delay_seconds": 120,
                    "instructions": ["c"],
                },
            ],
            "process_original_message": False,
        },
        "1 phút nữa A, 30s sau B, 30s sau C",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(wrapper_tasks), wrapper_tasks
    assert len(wrapper_tasks.get("tasks") or []) == 3

    no_invent = normalize_plan(
        {"task_hint": "schedule", "instructions": ["hello"], "cadence": "once"},
        "hello at 17:57",
        "Asia/Ho_Chi_Minh",
    )
    assert no_invent.get("cron_expr") in (None, "")
    assert plan_schema_ok(no_invent) is False

    print("OK classify skip + prior strip; LLM JSON schedule SoT; no regex heuristic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
