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
    print("OK schedule classify heuristic + prior strip + 400 skip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
