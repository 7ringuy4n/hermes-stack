# -*- coding: utf-8 -*-
"""Unit: schedule delivery mode + group ref cleaning (no docker)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from channels_client import _clean_group_ref, extract_target_group_ref  # noqa: E402
from schedule_client import fire_text_from_plan, schedule_delivery_mode  # noqa: E402


def test_clean_and_extract() -> None:
    assert _clean_group_ref("zalo LC group") == "LC group"
    assert _clean_group_ref("LC group") == "LC group"
    plan = {"target_channel": "zalo lc group"}
    assert extract_target_group_ref("ignored", plan) == "lc group"
    print("PASS clean/extract target_channel strips zalo prefix")


def test_delivery_and_fire_text() -> None:
    text = (
        "2 phút nữa gửi vào zalo lc group nội dung: "
        "xuân chưa tới nhưng lòng phơi phới khi xuân về"
    )
    plan = {
        "task_hint": "schedule",
        "schedule_delivery": "verbatim",
        "message": "xuân chưa tới nhưng lòng phơi phới khi xuân về",
        "instructions": ["sẽ gửi tin nhắn vào nhóm"],
        "target_channel": "LC group",
    }
    assert schedule_delivery_mode(plan, text) == "verbatim"
    assert fire_text_from_plan(plan, text).startswith("xuân chưa tới")
    # Host safety-net without classify field
    plan2 = {"message": "hello", "instructions": ["hello"]}
    assert schedule_delivery_mode(plan2, text) == "verbatim"
    assert schedule_delivery_mode({"schedule_delivery": "process"}, "lúc 6h kiểm tra thời tiết") == "process"
    print("PASS schedule_delivery + fire_text prefer verbatim body")


def main() -> int:
    try:
        test_clean_and_extract()
        test_delivery_and_fire_text()
    except AssertionError as e:
        print(f"FAIL {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
