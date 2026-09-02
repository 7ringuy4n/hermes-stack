#!/usr/bin/env python3
"""Unit: search+image host gates use classify RENDER contract only."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify_client import (  # noqa: E402
    plan_allows_search_then_info_card,
    plan_allows_search_then_weather_scene,
    plan_image_render_mode,
)


def test_render_contract_gates() -> None:
    labeled = {
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
    assert plan_image_render_mode(labeled) == "labeled-scene"
    assert plan_allows_search_then_info_card(labeled)
    assert not plan_allows_search_then_weather_scene(labeled)

    weather_scene = {
        "ok": True,
        "task_hint": "tool",
        "instructions": [
            "weather Ho Chi Minh City current forecast",
            "RENDER: weather-scene\nSCENE: Ho Chi Minh City skyline at dusk",
        ],
        "task_details": [
            {"task_type": "search", "skill": "web_search"},
            {"task_type": "media_generation", "output_type": "image"},
        ],
    }
    assert plan_image_render_mode(weather_scene) == "weather-scene"
    assert plan_allows_search_then_weather_scene(weather_scene)
    assert not plan_allows_search_then_info_card(weather_scene)

    prose_only = {
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
    assert plan_image_render_mode(prose_only) == ""
    assert not plan_allows_search_then_info_card(prose_only)
    assert not plan_allows_search_then_weather_scene(prose_only)


def main() -> None:
    test_render_contract_gates()
    print("OK labeled_weather_gate_unit")


if __name__ == "__main__":
    main()
