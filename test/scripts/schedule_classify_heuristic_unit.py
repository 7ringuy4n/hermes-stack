# -*- coding: utf-8 -*-
"""Schedule heuristic + classify skip HTTP codes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))

from classify import (  # noqa: E402
    _CLASSIFY_SKIP_HTTP,
    normalize_plan,
    plan_schema_ok,
    schedule_heuristic_plan,
)


def main() -> int:
    assert 503 in _CLASSIFY_SKIP_HTTP and 502 in _CLASSIFY_SKIP_HTTP
    text = (
        "đặt lịch chạy một lần lúc 20:17 với nội dung chúc mọi người một buổi tối tốt lành "
        "bên gia đình, 30 giây sau tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất "
        "kèm theo thông tin thời tiết Hồ Chí Minh hiện tại"
    )
    raw = schedule_heuristic_plan(text)
    assert raw and raw["cadence"] == "once" and raw["cron_expr"] == "17 20 * * *", raw
    assert "chúc mọi người" in raw["instructions"][0]
    plan = normalize_plan(raw, text, "Asia/Ho_Chi_Minh")
    assert plan_schema_ok(plan), plan
    assert plan["task_hint"] == "schedule" and plan["cron_expr"] == "17 20 * * *"

    daily = schedule_heuristic_plan("đặt lịch hằng ngày lúc 07:30 nội dung chào buổi sáng")
    assert daily and daily["cadence"] == "daily" and daily["cron_expr"] == "30 7 * * *", daily

    assert schedule_heuristic_plan("xin chào") is None
    print("OK schedule classify heuristic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
