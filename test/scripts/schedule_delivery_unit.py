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
    # Without classify target_channel, host must not invent a group from prose.
    assert extract_target_group_ref(DAILY, None) == ""
    assert extract_target_group_ref(DAILY, {}) == ""
    hydr = (
        "[Prior conversation]\n"
        "Assistant: Đã lưu lịch → nhóm Family @ 14:01\n"
        "[/Prior conversation]\n\n"
        + DAILY
    )
    assert extract_target_group_ref(hydr, {"target_channel": "LC group"}).lower() == "lc group"
    print("PASS clean/extract target_channel from classify only")


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
    assert schedule_delivery_mode(
        {"task_hint": "schedule", "schedule_delivery": "transform", "instructions": ["dịch hello"]},
        "30s nữa dịch hello",
    ) == "process"
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


def test_dictated_send_body_keeps_verbatim() -> None:
    """Classify verbatim must survive payload words that look like skills."""
    body = "không cần chit chat, chỉ mô tả sự cô đơn trong im lặng"
    original = f"1 phút nữa nhắn tôi nội dung:{body}"
    plan = {
        "task_hint": "schedule",
        "schedule_delivery": "verbatim",
        "schedule_form": "once_after",
        "delay_seconds": 60,
        "message": body,
        "instructions": [body],
    }
    assert not plan_is_task_work(plan)
    assert schedule_delivery_mode(plan, original) == "verbatim"
    assert fire_text_from_plan(plan, original) == body
    print("PASS dictated send-body stays verbatim")


def test_group_describe_trusts_classify_process() -> None:
    """Host trusts classify process + inner instructions; never fires the ask."""
    original = (
        "1 phút nữa gửi vào Zalo LC Group mô tả sự cô đơn khi không ai biết đến trợ lý"
    )
    inner = "mô tả sự cô đơn khi không ai biết đến trợ lý"
    plan = {
        "task_hint": "schedule",
        "schedule_delivery": "process",
        "schedule_form": "once_after",
        "delay_seconds": 60,
        "target_channel": "LC group",
        "message": inner,
        "instructions": [inner],
    }
    assert schedule_delivery_mode(plan, original) == "process"
    fire = fire_text_from_plan(plan, original)
    assert fire == inner
    assert "1 phút" not in fire and "gửi vào" not in fire.lower()
    # create-ask must not be used as fire_text when it equals the inbound bubble
    bad = {
        "schedule_delivery": "verbatim",
        "message": original,
        "instructions": [original],
    }
    assert fire_text_from_plan(bad, original) == ""
    assert fire_text_from_plan(
        {"schedule_delivery": "verbatim", "message": "hello world", "instructions": ["hello world"]},
        "1 phút nữa nhắn tôi nội dung: hello world",
    ) == "hello world"
    print("PASS host trusts classify process; refuse fire_text==full ask")


def main() -> int:
    try:
        test_clean_and_extract()
        test_verbatim_send_body()
        test_task_noidung_never_verbatim()
        test_process_explicit()
        test_dictated_send_body_keeps_verbatim()
        test_group_describe_trusts_classify_process()
    except AssertionError as e:
        print(f"FAIL {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
