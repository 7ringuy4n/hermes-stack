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
    failed = normalize_plan({"ok": False, "error": "classify_llm_failed"}, "1. a\n2. b", "Asia/Ho_Chi_Minh")
    assert failed["ok"] is False
    assert failed["instructions"] == []
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
    know = normalize_plan(
        {"task_hint": "knowledge", "instructions": ["labsolution"]},
        "cite labsolution",
        "Asia/Ho_Chi_Minh",
    )
    assert know["task_hint"] == "knowledge"
    assert know["instructions"] == ["labsolution"]
    print("llm_classify_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
