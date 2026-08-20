# -*- coding: utf-8 -*-
"""Unit: LLM classify JSON protocol validation. No host identity."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "workflow"))

from classify_client import normalize_plan, valid_cron  # noqa: E402


def main() -> int:
    assert valid_cron("54 13 * * *") == "54 13 * * *"
    assert valid_cron("hằng ngày lúc 13:54") is None
    assert valid_cron("0 6 * * * extra") is None
    blocked = normalize_plan({"task_hint": "SECRET", "instructions": ["x"]}, "x", "Asia/Ho_Chi_Minh")
    assert blocked["task_hint"] == "unknown"
    chat_alias = normalize_plan(
        {"task_hint": "chat", "instructions": ["hi"] * 50, "process_original_message": True},
        "hi",
        "Asia/Ho_Chi_Minh",
    )
    assert chat_alias["task_hint"] == "normal"
    assert chat_alias["instructions"] == ["hi"]
    failed = normalize_plan({"ok": False, "error": "classify_llm_failed"}, "1. a\n2. b", "Asia/Ho_Chi_Minh")
    assert failed["ok"] is False
    assert failed["instructions"] == []
    assert failed["response_mode"] == "confirm"
    no_cron = normalize_plan(
        {"task_hint": "schedule", "instructions": ["hello"], "cadence": "once"},
        "hello at 17:57",
        "Asia/Ho_Chi_Minh",
    )
    assert no_cron["ok"] is False
    details = normalize_plan(
        {
            "task_hint": "schedule",
            "instructions": ["chào", "tóm tắt thời tiết", "vẽ ảnh theo thời tiết"],
            "cadence": "once",
            "cron_expr": "57 17 * * *",
            "task_details": [
                {"execution_class": "interactive", "task_type": "chat", "depends_on": []},
                {"execution_class": "async", "task_type": "search", "depends_on": []},
                {"execution_class": "async", "task_type": "media_generation", "depends_on": [1]},
            ],
        },
        "ignored",
        "Asia/Ho_Chi_Minh",
    )
    assert details["cron_expr"] == "57 17 * * *"
    assert details["task_details"][2]["depends_on"] == [1]
    assert details["task_details"][2]["task_type"] == "media_generation"
    poster = normalize_plan(
        {
            "task_hint": "tool",
            "instructions": [
                "Vẽ hình Thành phố Hồ Chí Minh dựa trên tình hình thời tiết thực tế hiện tại, "
                "trên hình thể hiện ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất và thông tin "
                "tình hình thời tiết hiện tại, bằng tiếng Việt."
            ],
        },
        "ignored",
        "Asia/Ho_Chi_Minh",
    )
    assert poster["task_hint"] == "tool"
    assert len(poster["instructions"]) == 1
    assert "E10 RON95" in poster["instructions"][0]
    media = normalize_plan(
        {
            "task_hint": "tool",
            "execution_class": "async",
            "task_type": "media_generation",
            "response_mode": "ack_then_deliver",
            "instructions": ["Draw HCMC weather"],
        },
        "ignored",
        "Asia/Ho_Chi_Minh",
    )
    assert media["execution_class"] == "async"
    assert media["response_mode"] == "ack_then_deliver"
    hello = normalize_plan(
        {"task_hint": "normal", "instructions": ["Hello"]},
        "Hello",
        "Asia/Ho_Chi_Minh",
    )
    assert hello["execution_class"] == "interactive"
    assert hello["response_mode"] == "direct"
    sched = normalize_plan(
        {
            "task_hint": "schedule",
            "instructions": ["hello", "image"],
            "cadence": "daily",
            "cron_expr": "0 8 * * *",
        },
        "ignored",
        "Asia/Ho_Chi_Minh",
    )
    assert sched["task_hint"] == "schedule"
    assert sched["instructions"] == ["hello", "image"]
    assert sched["cron_expr"] == "0 8 * * *"
    once = normalize_plan(
        {
            "task_hint": "schedule",
            "instructions": [
                "Gửi một tin nhắn chào buổi sáng đến mọi người.",
                "Tóm tắt ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất không trích dẫn nguồn",
                "Tóm tắt ngắn gọn thông tin tình hình thời tiết Hồ Chí Minh hiện tại",
            ],
            "cadence": "once",
            "cron_expr": "24 11 * * *",
        },
        "ignored",
        "Asia/Ho_Chi_Minh",
    )
    assert once["task_hint"] == "schedule"
    assert once["cadence"] == "once"
    assert once["cron_expr"] == "24 11 * * *"
    assert len(once["instructions"]) == 3
    assert "E10 RON95" in once["instructions"][1]
    assert "thời tiết" in once["instructions"][2]
    four = normalize_plan(
        {
            "task_hint": "schedule",
            "instructions": [
                "Gửi tin nhắn chào",
                "Tìm và tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất",
                "Tìm và tóm tắt thời tiết TP.HCM hiện tại",
                "Vẽ tranh TP.HCM phản ánh đúng thời tiết lúc đó và gửi ảnh",
            ],
            "cadence": "once",
            "cron_expr": "35 20 * * *",
        },
        "ignored",
        "Asia/Ho_Chi_Minh",
    )
    assert len(four["instructions"]) == 4
    assert "chào" in four["instructions"][0]
    assert "E10 RON95" in four["instructions"][1]
    assert "thời tiết" in four["instructions"][2]
    assert "Vẽ" in four["instructions"][3] or "ảnh" in four["instructions"][3]
    know = normalize_plan(
        {"task_hint": "knowledge", "instructions": ["labsolution"]},
        "cite labsolution",
        "Asia/Ho_Chi_Minh",
    )
    assert know["task_hint"] == "knowledge"
    assert know["instructions"] == ["labsolution"]
    once_2113 = normalize_plan(
        {
            "task_hint": "schedule",
            "instructions": [
                "Gửi một tin nhắn chào đến mọi người.",
                "Tóm tắt ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất",
                "Tóm tắt ngắn gọn thông tin tình hình thời tiết hiện tại",
                "Vẽ hình Thành phố Hồ Chí Minh dựa trên tình hình thời tiết thực tế hiện tại",
            ],
            "cadence": "once",
            "cron_expr": "13 21 * * *",
            "task_details": [
                {"execution_class": "interactive", "task_type": "chat", "depends_on": []},
                {"execution_class": "async", "task_type": "search", "depends_on": []},
                {"execution_class": "async", "task_type": "search", "depends_on": []},
                {"execution_class": "async", "task_type": "media_generation", "depends_on": [2]},
            ],
        },
        "ignored",
        "Asia/Ho_Chi_Minh",
    )
    assert once_2113["ok"] is True
    assert once_2113["cron_expr"] == "13 21 * * *"
    assert once_2113["cadence"] == "once"
    assert len(once_2113["instructions"]) == 4
    assert once_2113["task_details"][3]["depends_on"] == [2]
    assert sched["skill"] == "schedule"
    assert sched["process_original_message"] is False
    search = normalize_plan(
        {"task_hint": "search", "instructions": ["Tìm giá xăng"]},
        "Tìm giá xăng",
        "Asia/Ho_Chi_Minh",
    )
    assert search["skill"] == "web_search"
    assert search["process_original_message"] is True
    print("llm_classify_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
