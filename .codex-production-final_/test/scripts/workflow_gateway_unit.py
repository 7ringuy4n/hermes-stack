# -*- coding: utf-8 -*-
"""Unit: direct Hermes API workflow parsing helpers (no network)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "gateway" / "api-gateway"))
sys.path.insert(0, str(ROOT / "test" / "scripts"))

import app  # noqa: E402
from classify_fixtures import install_unit_planner  # noqa: E402

install_unit_planner()


def main() -> int:
    payload = {
        "model": "gpt-test",
        "messages": [
            {"role": "system", "content": "You are Hermes."},
            {
                "role": "user",
                "content": "Thực hiện: 1. Tìm giá USD hiện tại 2. Vẽ hình HCMC 3. Cập nhật giá xăng",
            },
        ],
    }
    text = app._latest_user_text(payload)
    if "USD" not in text:
        print("FAIL latest user text", text)
        return 1
    parts = app._plan_instructions(text)
    if len(parts) != 3 or "xăng" not in parts[2]:
        print("FAIL plan instructions", parts)
        return 1
    print("PASS gateway multi-request plan")

    cron_text = (
        "Tạo lịch hằng ngày lúc 06:00 GMT+7\n"
        "1. Nhắc thức dậy\n"
        "2. Vẽ hình thời tiết HCMC\n"
        "3. Báo giá xăng"
    )
    if not app._looks_like_schedule(cron_text):
        print("FAIL schedule detect GMT+7")
        return 1
    print("PASS gateway schedule detect GMT+7")

    wf = {
        "id": "wf_test",
        "jobs": [
            {"result": {"text": "USD is 25,000 VND."}},
            {"result": {"text": "Attached HCMC weather image."}},
            {"result": {"text": "E5 and RON95 prices updated."}},
        ],
    }
    agg = app._aggregate_workflow_text(wf)
    if "1. USD" not in agg or "3. E5" not in agg:
        print("FAIL aggregate workflow text", agg)
        return 1
    print("PASS gateway aggregate workflow text")

    plenty = (
        "Thực hiện:\n"
        "1. Gửi tin chào buổi sáng\n"
        "2. Vẽ hình thời tiết HCMC\n"
        "3. Cập nhật giá xăng E5 RON92 và E10 RON95\n"
        "4. Báo tỷ giá USD/VND\n"
        "5. Tóm tắt lịch hôm nay\n"
        "6. Nhắc uống nước"
    )
    plenty_parts = app._plan_instructions(plenty)
    if len(plenty_parts) != 6 or "USD" not in plenty_parts[3]:
        print("FAIL gateway plenty plan", plenty_parts)
        return 1
    print("PASS gateway plenty 6-item plan")

    same_clock = (
        "hằng ngày lúc 13:54 GMT+7\n"
        "1. wakeup 6:00 AM GMT +7\n"
        "2. HCMC image\n"
        "3. fuel\n"
        "4. USD\n"
        "5. calendar\n"
        "6. water"
    )
    other_clock = (
        "hằng ngày lúc 12:00 GMT+7\n"
        "1. noon ping\n"
        "2. HCMC image\n"
        "3. fuel"
    )
    if not app._looks_like_schedule(same_clock) or not app._looks_like_schedule(other_clock):
        print("FAIL gateway schedule detect same/different clocks")
        return 1
    print("PASS gateway schedule detect 13:54 and 12:00")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
