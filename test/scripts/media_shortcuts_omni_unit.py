#!/usr/bin/env python3
"""Unit tests for scenic Omni image-gen helpers (media_shortcuts)."""
from __future__ import annotations

import importlib.util
import json
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
    try:
        assert mod._omni_image_gen_model() == "image-gen"
    finally:
        os.environ.pop("IMAGE_GEN_COMBO", None)


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
        "Ho Chi Minh City skyline at evening, city lights illuminated",
        ["Temperature: 28C", "Humidity: 80%", "Partly cloudy"],
    )
    low = prompt.lower()
    assert "caption board" not in low
    assert "no readable text" in low
    assert "no letters" in low
    assert "ho chi minh city" in low
    assert "evening" in low or "city lights" in low


def test_labeled_scene_prompt_keeps_board() -> None:
    prompt = mod._labeled_scene_prompt("City plaza", ["Temp: 30C"])
    assert "information board" in prompt.lower() or "readable" in prompt.lower()


def test_combo_failover_tries_combo_then_members() -> None:
    calls: list[str] = []
    original = mod._omni_request_image_blob_once

    def fake_once(**kwargs):
        candidate = kwargs.get("model", "")
        calls.append(candidate)
        if candidate == "ai-box/wan2.7-image-pro":
            return b"\x89PNG-fake-blob"
        return None

    mod._omni_request_image_blob_once = fake_once
    try:
        blob = mod._omni_request_image_blob(
            base="http://omni/v1",
            key="k",
            model="image-gen",
            scene="hcm",
            size="1280x720",
            timeout=30,
            combo_members=["pollinations/flux", "ai-box/wan2.7-image-pro"],
        )
    finally:
        mod._omni_request_image_blob_once = original

    assert blob == b"\x89PNG-fake-blob"
    assert calls == ["image-gen", "pollinations/flux", "ai-box/wan2.7-image-pro"]


def test_combo_member_models_parses_v1_combos() -> None:
    payload = {
        "data": [
            {"name": "other", "models": [{"model": "x/a"}]},
            {"name": "image-gen", "models": [{"model": "ai-box/wan"}, {"model": "ai-box/wan"}]},
        ]
    }

    captured = {"url": None}

    class _Resp:
        def __init__(self, data):
            self._data = data

        def read(self):
            return json.dumps(self._data).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(req, timeout=0):
        captured["url"] = req.full_url
        return _Resp(payload)

    original = mod.urllib.request.urlopen
    mod.urllib.request.urlopen = fake_open
    try:
        members = mod._omni_v1_combo_member_models("http://omni/v1", "k", "image-gen")
    finally:
        mod.urllib.request.urlopen = original

    assert captured["url"] == "http://omni/v1/combos"
    assert members == ["ai-box/wan"]


def main() -> None:
    test_image_gen_timeout_default()
    test_image_gen_timeout_clamped()
    test_image_gen_size_default()
    test_image_gen_model_combo()
    test_image_gen_model_uses_member_id_when_combo_is_member()
    test_image_quality_mins_hd()
    test_image_quality_mins_full_hd()
    test_media_out_candidates_shared_first()
    test_weather_scene_visual_prompt_no_text_board()
    test_labeled_scene_prompt_keeps_board()
    test_combo_failover_tries_combo_then_members()
    test_combo_member_models_parses_v1_combos()
    print("OK media_shortcuts_omni_unit")


if __name__ == "__main__":
    main()
