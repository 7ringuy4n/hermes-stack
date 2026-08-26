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
    assert "PRIMARY DUTY" in system
    assert "SCHEDULE POLICY" in system
    assert "Host does not scan" in system
    assert "FILE / MEDIA POLICY" in system
    assert "DELIVERY POLICY" in system
    assert "OUTPUT SCHEMA" in system
    assert env.get("parts") == ["core", "schedule", "media", "delivery", "schema"]
    assert str(CFG_PATH).replace("\\", "/").endswith("skills/classify/classify.json"), CFG_PATH

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
