#!/usr/bin/env python3
"""Unit tests for scenic Omni image-gen helpers (media_shortcuts)."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))
spec = importlib.util.spec_from_file_location(
    "media_shortcuts",
    ROOT / "hermes" / "main" / "plugins" / "zalo" / "media_shortcuts.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_image_gen_timeout_default() -> None:
    os.environ.pop("OMNI_IMAGE_GEN_TIMEOUT_S", None)
    assert mod._omni_image_gen_timeout_s() == 240


def test_image_gen_timeout_clamped() -> None:
    os.environ["OMNI_IMAGE_GEN_TIMEOUT_S"] = "9999"
    try:
        assert mod._omni_image_gen_timeout_s() == 600
    finally:
        os.environ.pop("OMNI_IMAGE_GEN_TIMEOUT_S", None)


def test_image_gen_size_default() -> None:
    os.environ.pop("OMNI_IMAGE_GEN_SIZE", None)
    assert mod._omni_image_gen_size() == "1280x720"


def test_image_gen_model_combo() -> None:
    os.environ["IMAGE_GEN_COMBO"] = "image-gen"
    os.environ.pop("IMAGE_GEN_HEAD_MEMBER", None)
    try:
        assert mod._omni_image_gen_model() == "image-gen"
    finally:
        os.environ.pop("IMAGE_GEN_COMBO", None)


def test_image_gen_model_uses_head_member() -> None:
    os.environ["IMAGE_GEN_COMBO"] = "image-gen"
    os.environ["IMAGE_GEN_HEAD_MEMBER"] = "img-gen/wan2.7-image-pro"
    try:
        assert mod._omni_image_gen_model() == "img-gen/wan2.7-image-pro"
    finally:
        os.environ.pop("IMAGE_GEN_COMBO", None)
        os.environ.pop("IMAGE_GEN_HEAD_MEMBER", None)


def test_image_gen_model_uses_member_id_when_combo_is_member() -> None:
    os.environ["IMAGE_GEN_COMBO"] = "img-gen/qwen-image-3.0"
    os.environ.pop("IMAGE_GEN_HEAD_MEMBER", None)
    try:
        assert mod._omni_image_gen_model() == "img-gen/qwen-image-3.0"
    finally:
        os.environ.pop("IMAGE_GEN_COMBO", None)


def test_image_quality_mins_hd() -> None:
    min_w, min_h, min_bytes = mod._omni_image_quality_mins("1280x720")
    assert min_w == 640 and min_h == 360 and min_bytes == 80_000


def test_image_quality_mins_full_hd() -> None:
    min_w, min_h, _ = mod._omni_image_quality_mins("1920x1080")
    assert min_w == 960 and min_h == 540


def test_media_out_candidates_shared_first() -> None:
    os.environ["HERMES_SHARED_DATA"] = "/opt/data"
    os.environ.pop("HERMES_HOME", None)
    os.environ.pop("MEDIA_OUT_DIR", None)
    try:
        roots = [p.as_posix() for p in mod._media_out_candidates()]
        assert roots[0] == "/opt/data/media/out"
        assert "/data/assistant/media/out" in roots
    finally:
        os.environ.pop("HERMES_SHARED_DATA", None)


def test_weather_scene_visual_prompt_no_text_board() -> None:
    prompt = mod._weather_scene_visual_prompt(
        "Ho Chi Minh City skyline",
        ["Temperature: 28C", "Humidity: 80%", "Partly cloudy"],
    )
    low = prompt.lower()
    assert "caption board" not in low
    assert "readable text" in low or "no readable text" in low
    assert "no letters" in low
    assert "ho chi minh city" in low


def test_weather_visual_cues_rain() -> None:
    cues = mod._weather_visual_cues(["Heavy rain showers", "Humid"])
    blob = " ".join(cues).lower()
    assert "rain" in blob or "wet" in blob


def test_labeled_scene_prompt_keeps_board() -> None:
    prompt = mod._labeled_scene_prompt("City plaza", ["Temp: 30C"])
    assert "information board" in prompt.lower() or "readable" in prompt.lower()


def main() -> None:
    test_image_gen_timeout_default()
    test_image_gen_timeout_clamped()
    test_image_gen_size_default()
    test_image_gen_model_combo()
    test_image_gen_model_uses_head_member()
    test_image_gen_model_uses_member_id_when_combo_is_member()
    test_image_quality_mins_hd()
    test_image_quality_mins_full_hd()
    test_media_out_candidates_shared_first()
    test_weather_scene_visual_prompt_no_text_board()
    test_weather_visual_cues_rain()
    test_labeled_scene_prompt_keeps_board()
    print("OK media_shortcuts_omni_unit")


if __name__ == "__main__":
    main()
