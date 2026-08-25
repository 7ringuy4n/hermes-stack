# -*- coding: utf-8 -*-
"""Schedule heuristic + classify skip HTTP codes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))

from classify import (  # noqa: E402
    _CLASSIFY_SKIP_HTTP,
    _classify_body_is_schema_dead,
    heuristic_plan,
    normalize_plan,
    plan_schema_ok,
    schedule_heuristic_plan,
    strip_prior_for_classify,
)


def main() -> int:
    assert 400 in _CLASSIFY_SKIP_HTTP and 503 in _CLASSIFY_SKIP_HTTP
    assert _classify_body_is_schema_dead(
        400,
        '{"errors":[{"message":"AiError: Bad input: required properties at \'/\' are \'prompt\'"}]}',
    )
    wrapped = (
        "[Prior conversation]\nUser: tạo pdf\n[/Prior conversation]\n\n"
        "đặt lịch chạy một lần lúc 20:17 với nội dung chúc mọi người buổi tối"
    )
    bare = strip_prior_for_classify(wrapped)
    assert "[Prior conversation]" not in bare
    assert "đặt lịch" in bare
    raw = schedule_heuristic_plan(bare)
    assert raw and raw["cron_expr"] == "17 20 * * *", raw
    plan = normalize_plan(raw, bare, "Asia/Ho_Chi_Minh")
    assert plan_schema_ok(plan)
    sys.path.insert(0, str(ROOT / "test" / "scripts"))
    from classify_fixtures import FIXTURE_EN4, FIXTURE_INFOGRAPHIC_VI, FIXTURE_INFOGRAPHIC_DAILY  # noqa: E402

    en4 = normalize_plan(heuristic_plan(FIXTURE_EN4), FIXTURE_EN4, "Asia/Ho_Chi_Minh")
    assert en4["task_hint"] == "tool" and len(en4["instructions"]) == 4, en4
    info = normalize_plan(heuristic_plan(FIXTURE_INFOGRAPHIC_VI), FIXTURE_INFOGRAPHIC_VI, "Asia/Ho_Chi_Minh")
    assert info["task_hint"] == "tool" and len(info["instructions"]) == 1, info
    daily = normalize_plan(
        heuristic_plan(FIXTURE_INFOGRAPHIC_DAILY), FIXTURE_INFOGRAPHIC_DAILY, "Asia/Ho_Chi_Minh"
    )
    assert daily["task_hint"] == "schedule" and daily["cron_expr"] == "0 7 * * *", daily

    daily_lc = (
        "đặt lịch chạy hằng ngày lúc 06:00 vào Zalo LC Group nội dung: "
        "mô tả 1 bài thơ ngắn 4 dòng về trời xanh gió mát chim hót líu lo chào ngày mới, "
        "cập nhật giá xăng E5 RON92 và E10 RON95 mới nhất, "
        "dự báo thời tiết hồ chí minh trong ngày"
    )
    raw_lc = schedule_heuristic_plan(daily_lc)
    assert raw_lc and raw_lc["cron_expr"] == "0 6 * * *", raw_lc
    assert raw_lc.get("schedule_delivery") == "process", raw_lc
    assert (raw_lc.get("target_channel") or "").lower() == "lc group", raw_lc
    # Heuristic does not skill-split (no verb NLU); LLM classify owns multi-instruction.
    assert len(raw_lc.get("instructions") or []) >= 1, raw_lc
    plan_lc = normalize_plan(raw_lc, daily_lc, "Asia/Ho_Chi_Minh")
    assert plan_schema_ok(plan_lc)
    assert plan_lc.get("schedule_delivery") == "process"
    assert (plan_lc.get("target_channel") or "").lower() == "lc group"

    rel = "1 phút nữa gửi vào Zalo LC Group: chào buổi sáng"
    raw_rel = schedule_heuristic_plan(rel)
    assert raw_rel and raw_rel.get("schedule_form") == "once_after", raw_rel
    assert raw_rel.get("delay_seconds") == 60, raw_rel
    assert not raw_rel.get("cron_expr"), raw_rel
    plan_rel = normalize_plan(raw_rel, rel, "Asia/Ho_Chi_Minh")
    assert plan_schema_ok(plan_rel)
    assert plan_rel.get("delay_seconds") == 60
    assert not plan_rel.get("cron_expr")

    send_me = (
        "1 phút nữa nhắn tôi nội dung: không cần chit chat, "
        "chỉ mô tả sự cô đơn trong im lặng"
    )
    raw_send = schedule_heuristic_plan(send_me)
    assert raw_send and raw_send.get("schedule_form") == "once_after", raw_send
    assert raw_send.get("delay_seconds") == 60, raw_send
    assert raw_send.get("schedule_delivery") == "verbatim", raw_send
    assert len(raw_send.get("instructions") or []) == 1, raw_send
    plan_send = normalize_plan(raw_send, send_me, "Asia/Ho_Chi_Minh")
    assert plan_schema_ok(plan_send)
    assert plan_send.get("schedule_delivery") == "verbatim"

    group_desc = (
        "1 phút nữa gửi vào Zalo LC Group mô tả sự cô đơn khi không ai biết đến trợ lý"
    )
    raw_gd = schedule_heuristic_plan(group_desc)
    assert raw_gd and raw_gd.get("schedule_form") == "once_after", raw_gd
    assert raw_gd.get("delay_seconds") == 60, raw_gd
    # No nội dung: marker → process (LLM owns inner body + destination).
    assert raw_gd.get("schedule_delivery") == "process", raw_gd
    plan_gd = normalize_plan(raw_gd, group_desc, "Asia/Ho_Chi_Minh")
    assert plan_schema_ok(plan_gd)
    assert plan_gd.get("schedule_delivery") == "process"

    print("OK schedule classify heuristic + prior strip + 400 skip + once_after")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
