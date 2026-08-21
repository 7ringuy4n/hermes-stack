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
    print("OK schedule classify heuristic + prior strip + 400 skip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
