# -*- coding: utf-8 -*-
"""Unit: host media shortcut gate blocks Hermes/workflow fallthrough."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify_client import (  # noqa: E402
    normalize_plan,
    plan_media_shortcut_gate,
    plan_allows_scene_image,
)


def test_scenic_plan_gate() -> None:
    raw = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "execution_class": "async",
        "response_mode": "ack_then_deliver",
        "skill": "media_file",
        "skill_action": "generate_media",
        "process_original_message": True,
        "instructions": [
            "SCENE: Da Lat city, Vietnam, photorealistic photograph, street-level view"
        ],
        "task_details": [
            {
                "execution_class": "async",
                "task_type": "media_generation",
                "response_mode": "ack_then_deliver",
            }
        ],
    }
    plan = normalize_plan(raw, "vẽ hình thành phố đà lạt", "Asia/Ho_Chi_Minh")
    assert plan_media_shortcut_gate(plan) == "scene_image", plan
    assert plan_allows_scene_image(plan) is True
    assert plan.get("process_original_message") is False


def test_pure_media_process_false() -> None:
    raw = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "execution_class": "async",
        "skill": "media_file",
        "instructions": ["SCENE: mountain lake at dawn"],
        "task_details": [{"task_type": "media_generation", "execution_class": "async"}],
    }
    plan = normalize_plan(raw, "vẽ hồ núi lúc bình minh", "Asia/Ho_Chi_Minh")
    assert plan.get("process_original_message") is False


def test_weather_on_image_gate() -> None:
    raw = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "execution_class": "async",
        "response_mode": "ack_then_deliver",
        "skill": "media_file",
        "skill_action": "generate_media",
        "output_type": "image",
        "instructions": [
            "current weather Ho Chi Minh City",
            "RENDER: weather-scene\nSCENE: Ho Chi Minh City street-level photograph, natural light\n- Nhiệt độ: 29°C\n- Độ ẩm: 70%",
        ],
        "task_details": [
            {"task_type": "search", "output_type": None},
            {"task_type": "media_generation", "output_type": "image"},
        ],
    }
    plan = normalize_plan(
        raw,
        "cập nhật thông tin thời tiết hồ chí minh, ghi thông tin lên hình góc trái bên dưới",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_media_shortcut_gate(plan) == "weather_scene", plan


def test_labeled_scene_still_gates_info_card() -> None:
    raw = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "execution_class": "async",
        "skill": "media_file",
        "skill_action": "generate_media",
        "output_type": "image",
        "instructions": [
            "fuel prices Ho Chi Minh",
            "RENDER: labeled-scene\nSCENE: plaza photograph\n- Xăng RON95: 21000",
        ],
        "task_details": [
            {"task_type": "search"},
            {"task_type": "media_generation", "output_type": "image"},
        ],
    }
    plan = normalize_plan(raw, "hình ảnh chứa thông tin giá xăng", "Asia/Ho_Chi_Minh")
    assert plan_media_shortcut_gate(plan) == "info_card", plan


def main() -> int:
    test_scenic_plan_gate()
    test_pure_media_process_false()
    test_weather_on_image_gate()
    test_labeled_scene_still_gates_info_card()
    print("media_shortcut_gate_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
