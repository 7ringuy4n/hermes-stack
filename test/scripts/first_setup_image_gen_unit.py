#!/usr/bin/env python3
"""Unit tests for image-gen combo member selection (first-setup-omnirouter)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "first_setup_omnirouter",
    ROOT / "scripts" / "main" / "first-setup-omnirouter.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def _row(mid: str, **caps) -> dict:
    return {"id": mid, "capabilities": caps or {}}


def test_aibox_image_models_whitelisted() -> None:
    for mid in (
        "img-gen/qwen-image-2.0",
        "image-gen/qwen-image-3.0-pro",
        "img-gen/wan2.7-image-pro",
    ):
        assert mod._is_aibox_image_generation_model(mid) is True
        assert mod._is_image_output_model(_row(mid)) is True
        assert mod._is_bad_image_gen_combo_member(mid) is False


def test_exclude_img_gen_namespace_junk() -> None:
    assert mod._is_image_gen_namespace_chat_model("img-gen/deepseek-v4-flash") is True
    assert mod._is_image_gen_namespace_junk("img-gen/deepseek-v4-flash") is True
    assert mod._is_bad_image_gen_combo_member("img-gen/deepseek-v4-flash") is True
    assert mod._is_image_gen_namespace_junk("img-gen/qwen-image-2.0") is False


def test_allow_aihorde_diffusion() -> None:
    mid = "aihorde/ICBINP - I Can't Believe It's Not Photography"
    assert mod._is_aihorde_diffusion_model_id(mid) is True
    assert mod._is_image_output_model(_row(mid, reasoning=True)) is True
    assert mod._is_bad_image_gen_combo_member(mid) is False


def test_allow_openrouter_flux() -> None:
    mid = "openrouter/black-forest-labs/flux.2-flex"
    assert mod._is_openrouter_image_model_id(mid) is True
    assert mod._is_image_output_model(_row(mid, tool_calling=True)) is True


def test_rank_prefers_aibox_over_horde() -> None:
    horde = "aihorde/ICBINP"
    aibox = "img-gen/qwen-image-3.0-pro"
    assert mod._rank_image_gen_model(aibox) < mod._rank_image_gen_model(horde)


def test_custom_image_model_action() -> None:
    assert mod._custom_image_model_action(None) == "add"
    assert (
        mod._custom_image_model_action(
            {"id": "qwen-image-2.0", "apiFormat": "images-generations", "supportedEndpoints": ["chat"]}
        )
        == "fix"
    )
    assert (
        mod._custom_image_model_action(
            {"id": "qwen-image-2.0", "apiFormat": "images-generations", "supportedEndpoints": ["images"]}
        )
        == ""
    )
    assert (
        mod._custom_image_model_action(
            {"id": "qwen-image-2.0", "apiFormat": "chat-completions", "supportedEndpoints": ["images"]}
        )
        == "fix"
    )


def test_aibox_image_provider_nodes_filter() -> None:
    fake_nodes = [
        {"id": "n1", "name": "AI Box", "prefix": "img-gen", "apiType": "images-generations"},
        {"id": "n2", "name": "chat", "prefix": "oc", "apiType": "chat-completions"},
        {"id": "n3", "name": "comfy", "prefix": "comfyui", "apiType": "comfyui"},
    ]

    captured = {}
    original_http = getattr(mod, "http_json", None)

    def fake_http(opener, method, url, body=None, timeout=25):
        captured["url"] = url
        return 200, {"nodes": fake_nodes}

    mod.http_json = fake_http
    try:
        nodes = mod._aibox_image_provider_nodes(object())
    finally:
        if original_http is not None:
            mod.http_json = original_http
        else:
            del mod.http_json
    ids = {n["id"] for n in nodes}
    assert "n1" in ids
    assert "n2" not in ids
    assert "n3" not in ids
    assert "/api/provider-nodes" in captured.get("url", "")


def main() -> None:
    test_aibox_image_models_whitelisted()
    test_exclude_img_gen_namespace_junk()
    test_allow_aihorde_diffusion()
    test_allow_openrouter_flux()
    test_rank_prefers_aibox_over_horde()
    test_custom_image_model_action()
    test_aibox_image_provider_nodes_filter()
    print("OK first_setup_image_gen_unit")


if __name__ == "__main__":
    main()
