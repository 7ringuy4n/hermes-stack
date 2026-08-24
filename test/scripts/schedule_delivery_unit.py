# -*- coding: utf-8 -*-
"""Unit: schedule delivery mode + group ref cleaning (no docker)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from channels_client import _clean_group_ref, extract_target_group_ref  # noqa: E402
from schedule_client import (  # noqa: E402
    fire_text_from_plan,
    plan_is_task_work,
    schedule_delivery_mode,
)

DAILY = (
    "đặt lịch chạy hằng ngày lúc 06:00 vào Zalo LC Group nội dung: "
    "mô tả 1 bài thơ ngắn 4 dòng về trời xanh gió mát chim hót líu lo chào ngày mới, "
    "cập nhật giá xăng E5 RON92 và E10 RON95 mới nhất, "
    "dự báo thời tiết hồ chí minh trong ngày"
)

POEM = (
    "2 phút nữa gửi vào zalo lc group nội dung: "
    "xuân chưa tới nhưng lòng phơi phới khi xuân về"
)


def test_clean_and_extract() -> None:
    assert _clean_group_ref("zalo LC group") == "LC group"
    assert _clean_group_ref("LC group") == "LC group"
    plan = {"target_channel": "zalo lc group"}
    assert extract_target_group_ref("ignored", plan) == "lc group"
    print("PASS clean/extract target_channel strips zalo prefix")


def test_verbatim_send_body() -> None:
    plan = {
        "task_hint": "schedule",
        "schedule_delivery": "verbatim",
        "message": "xuân chưa tới nhưng lòng phơi phới khi xuân về",
        "instructions": ["xuân chưa tới nhưng lòng phơi phới khi xuân về"],
        "target_channel": "LC group",
    }
    assert schedule_delivery_mode(plan, POEM) == "verbatim"
    assert fire_text_from_plan(plan, POEM).startswith("xuân chưa tới")
    print("PASS verbatim send-body poem")


def test_task_noidung_never_verbatim() -> None:
    plan = {
        "task_hint": "schedule",
        "schedule_delivery": "verbatim",  # mis-label must not win over split skills
        "cadence": "daily",
        "target_channel": "LC group",
        "message": DAILY.split("nội dung:", 1)[-1].strip(),
        "instructions": [
            "mô tả 1 bài thơ ngắn 4 dòng về trời xanh gió mát chim hót líu lo chào ngày mới",
            "cập nhật giá xăng E5 RON92 và E10 RON95 mới nhất",
            "dự báo thời tiết hồ chí minh trong ngày",
        ],
        "task_details": [
            {"task_type": "media_generation", "skill": "media_file"},
            {"task_type": "search", "skill": "web_search"},
            {"task_type": "search", "skill": "web_search"},
        ],
    }
    assert plan_is_task_work(plan)
    assert schedule_delivery_mode(plan, DAILY) == "process"
    fire = fire_text_from_plan(plan, DAILY)
    assert "giá xăng" in fire and "thời tiết" in fire
    assert fire.count("\n") >= 2
    print("PASS task noidung is process + split fire_text")


def test_process_explicit() -> None:
    assert (
        schedule_delivery_mode({"schedule_delivery": "process"}, "lúc 6h kiểm tra thời tiết")
        == "process"
    )
    print("PASS explicit process")


def main() -> int:
    try:
        test_clean_and_extract()
        test_verbatim_send_body()
        test_task_noidung_never_verbatim()
        test_process_explicit()
    except AssertionError as e:
        print(f"FAIL {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
