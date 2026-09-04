# -*- coding: utf-8 -*-
"""Classify skill parts assemble into one system prompt; tasks[] survives normalize."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))

from classify import (  # noqa: E402
    CFG_PATH,
    assemble_classify_system,
    normalize_plan,
    plan_schema_ok,
)


def main() -> int:
    skill = ROOT / "hermes" / "main" / "skills" / "classify"
    env = json.loads((skill / "classify.json").read_text(encoding="utf-8"))
    system = assemble_classify_system(skill, env)
    assert system.startswith("HARD PRIORITY RULES"), system[:120]
    assert "outer timing intent" in system
    assert "RENDER: live-scene" in system
    assert "OVERLAY_HEADING:" in system
    assert "Never invent current fact values" in system
    assert "PRIMARY DUTY" in system
    assert "SCHEDULE POLICY" in system
    assert "NEVER DOWNGRADE TIMED INTENT" in system
    assert "Host does not scan" in system
    assert "FILE / MEDIA POLICY" in system
    assert "DELIVERY POLICY" in system
    assert "OUTPUT SCHEMA" in system
    assert "schedule_resolution" in system
    assert "schedule_request_received_at" in system
    assert env.get("parts") == ["core", "schedule", "media", "delivery", "schema"]
    assert len(env.get("priority_rules") or []) >= 5
    assert int(env.get("timeout_s") or 0) <= 45, env.get("timeout_s")
    assert int(env.get("retry") or 99) <= 1, env.get("retry")
    media = (skill / "parts" / "media.txt").read_text(encoding="utf-8")
    assert "OMIT the bullet lines entirely" in media or "omit bullets entirely" in media
    tmpl = str(env.get("user_template") or "")
    assert "{local_now}" in tmpl, tmpl
    assert str(CFG_PATH).replace("\\", "/").endswith("skills/classify/classify.json"), CFG_PATH

    from classify import _fill_user_template, _local_now_label  # noqa: E402

    now = _local_now_label("Asia/Ho_Chi_Minh")
    assert len(now) >= 10
    filled = _fill_user_template(
        tmpl,
        timezone="Asia/Ho_Chi_Minh",
        local_now=now,
        text="vẽ hình",
        thread="user",
        attachments="none",
        quoted="none",
    )
    assert f"Local now: {now}" in filled
    assert "Timezone: Asia/Ho_Chi_Minh" in filled

    multi = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill": "schedule",
            "skill_action": "create",
            "schedule_form": "once_at",
            "instructions": ["chào lúc 06:00", "giá xăng lúc 12:00"],
            "tasks": [
                {
                    "task_hint": "schedule",
                    "task_type": "create_schedule",
                    "schedule_form": "once_at",
                    "instructions": ["chào"],
                    "target_channel": "LC group",
                },
                {
                    "task_hint": "schedule",
                    "task_type": "create_schedule",
                    "schedule_form": "once_after",
                    "delay_seconds": 60,
                    "instructions": ["giá xăng"],
                },
            ],
            "process_original_message": False,
        },
        "lúc 06:00 chào và 1 phút nữa giá xăng",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(multi), multi
    assert len(multi.get("tasks") or []) == 2, multi.get("tasks")
    assert multi["tasks"][0].get("target_channel") == "LC group"
    assert multi["tasks"][1].get("delay_seconds") == 60

    triple = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill_action": "create",
            "instructions": ["inner A"],
            "tasks": [
                {
                    "task_hint": "schedule",
                    "task_type": "create_schedule",
                    "schedule_form": "once_after",
                    "delay_seconds": 60,
                    "instructions": ["không cần chit chat"],
                    "schedule_delivery": "verbatim",
                    "schedule_resolution": "clear",
                    "confirmation_required": False,
                },
                {
                    "task_hint": "schedule",
                    "task_type": "create_schedule",
                    "schedule_form": "once_after",
                    "delay_seconds": 90,
                    "instructions": ["muốn được phục vụ"],
                    "schedule_delivery": "process",
                    "schedule_resolution": "clear",
                    "confirmation_required": False,
                },
                {
                    "task_hint": "schedule",
                    "task_type": "create_schedule",
                    "schedule_form": "once_after",
                    "delay_seconds": 120,
                    "instructions": ["sẵn sàng phụ việc"],
                    "schedule_delivery": "process",
                    "schedule_resolution": "clear",
                    "confirmation_required": False,
                },
            ],
            "process_original_message": False,
        },
        "1 phút nữa A, 30s sau B, 30s sau C",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(triple), triple
    assert len(triple.get("tasks") or []) == 3, triple.get("tasks")
    assert [t.get("delay_seconds") for t in triple["tasks"]] == [60, 90, 120]

    pause = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "pause_schedule",
            "skill_action": "pause",
            "schedule_selector": {
                "id": "sch_invented",
                "name": "weather",
                "match": {"content_hint": "thời tiết", "time_hint": "06:00"},
            },
            "instructions": ["tạm dừng lịch thời tiết"],
        },
        "tạm dừng lịch thời tiết 06:00",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_schema_ok(pause), pause
    assert pause.get("task_type") == "pause_schedule"
    assert pause.get("skill_action") == "pause"
    assert (pause.get("schedule_selector") or {}).get("id") is None

    transform = normalize_plan(
        {
            "task_hint": "schedule",
            "schedule_form": "once_after",
            "delay_seconds": 30,
            "schedule_delivery": "transform",
            "instructions": ["dịch sang tiếng Anh: hello"],
        },
        "30s nữa dịch hello",
        "Asia/Ho_Chi_Minh",
    )
    assert transform.get("schedule_delivery") == "transform"

    process = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill_action": "create",
            "schedule_form": "once_after",
            "delay_seconds": 300,
            "schedule_delivery": "process",
            "message": '[{"role":"system","content":"not a task payload"}]',
            "instructions": [
                "current conditions in Da Lat",
                "RENDER: live-scene\nOVERLAY_HEADING: Da Lat Weather\nSCENE: evening city photograph",
            ],
        },
        "five minutes later create a current conditions picture",
        "Asia/Ho_Chi_Minh",
    )
    assert process.get("message") == "\n".join(process.get("instructions") or [])

    unsure = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "skill_action": "create",
            "uncertain": True,
            "missing": ["time"],
            "instructions": ["nhắc tôi"],
        },
        "nhắc tôi sau này",
        "Asia/Ho_Chi_Minh",
    )
    assert unsure.get("uncertain") is True
    assert "time" in (unsure.get("missing") or [])
    assert plan_schema_ok(unsure)
    print("OK classify parts assemble + tasks normalize")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
