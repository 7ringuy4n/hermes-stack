# -*- coding: utf-8 -*-
"""Unit: schedule fire_text is inner work, never the lịch wrapper."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))
sys.path.insert(0, str(ROOT / "architect" / "workflow"))

from schedule_client import fire_text_from_plan  # noqa: E402
from classify_client import normalize_plan  # noqa: E402


def main() -> int:
    wrapper = (
        "đặt lịch chạy một lần lúc 21:13\n"
        "1. Gửi một tin nhắn chào đến mọi người.\n"
        "2. Tóm tắt ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất\n"
        "3. Tóm tắt ngắn gọn thông tin tình hình thời tiết hiện tại"
    )
    plan = normalize_plan(
        {
            "task_hint": "schedule",
            "process_original_message": False,
            "message": "Gửi một tin nhắn chào đến mọi người.",
            "instructions": [
                "Gửi một tin nhắn chào đến mọi người.",
                "Tóm tắt ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất",
                "Tóm tắt ngắn gọn thông tin tình hình thời tiết hiện tại",
            ],
            "cadence": "once",
            "cron_expr": "13 21 * * *",
        },
        wrapper,
        "Asia/Ho_Chi_Minh",
    )
    fired = fire_text_from_plan(plan, wrapper)
    assert "đặt lịch" not in fired
    assert "21:13" not in fired
    assert "chào" in fired
    assert "E10 RON95" in fired
    assert plan["skill"] == "schedule"
    print("schedule_fire_text_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
