#!/usr/bin/env python3
"""Unit: labeled weather-on-image host gate (classify_client)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify_client import (  # noqa: E402
    plan_allows_search_then_info_card,
    plan_allows_search_then_weather_scene,
    plan_requests_labeled_weather_on_image,
)


def test_labeled_weather_on_image_cues() -> None:
    plan = {
        "ok": True,
        "task_hint": "tool",
        "instructions": [
            "weather Ho Chi Minh City current forecast",
            "RENDER: labeled-scene\nSCENE: Ho Chi Minh City skyline",
        ],
        "task_details": [
            {"task_type": "search", "skill": "web_search"},
            {"task_type": "media_generation", "output_type": "image"},
        ],
    }
    assert plan_requests_labeled_weather_on_image(plan)
    assert plan_allows_search_then_info_card(plan)
    assert not plan_allows_search_then_weather_scene(plan)

    viet = {
        "ok": True,
        "task_hint": "tool",
        "instructions": [
            "dự báo thời tiết Hồ Chí Minh hiện tại",
            "vẽ hình Hồ Chí Minh và ghi thông tin thời tiết lên hình",
        ],
        "task_details": [
            {"task_type": "search", "skill": "web_search"},
            {"task_type": "media_generation", "output_type": "image"},
        ],
    }
    assert plan_requests_labeled_weather_on_image(viet)
    assert plan_allows_search_then_info_card(viet)


def main() -> None:
    test_labeled_weather_on_image_cues()
    print("OK labeled_weather_gate_unit")


if __name__ == "__main__":
    main()
