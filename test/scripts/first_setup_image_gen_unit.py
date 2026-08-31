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


def test_exclude_img_gen_namespace_chat() -> None:
    assert mod._is_image_gen_namespace_chat_model("img-gen/qwen-image-2.0") is True
    assert mod._is_image_gen_namespace_chat_model("img-gen/deepseek-v4-flash") is True
    assert mod._is_bad_image_gen_combo_member("img-gen/qwen-image-2.0") is True


def test_exclude_image_gen_namespace_chat() -> None:
    assert mod._is_image_gen_namespace_chat_model("image-gen/qwen-image-2.0") is True
    assert mod._is_image_gen_namespace_chat_model("image-gen/deepseek-v4-flash") is True
    assert mod._is_image_output_model(_row("image-gen/qwen-image-2.0", reasoning=True)) is False
    assert mod._is_bad_image_gen_combo_member("image-gen/deepseek-v4-flash") is True


def test_allow_aihorde_diffusion() -> None:
    mid = "aihorde/ICBINP - I Can't Believe It's Not Photography"
    assert mod._is_aihorde_diffusion_model_id(mid) is True
    assert mod._is_image_output_model(_row(mid, reasoning=True)) is True
    assert mod._is_bad_image_gen_combo_member(mid) is False


def test_allow_openrouter_flux() -> None:
    mid = "openrouter/black-forest-labs/flux.2-flex"
    assert mod._is_openrouter_image_model_id(mid) is True
    assert mod._is_image_output_model(_row(mid, tool_calling=True)) is True


def test_rank_prefers_icbinp_over_aibox() -> None:
    horde = "aihorde/ICBINP"
    chat = "image-gen/qwen-image-2.0"
    assert mod._rank_image_gen_model(horde) < mod._rank_image_gen_model(chat)


def main() -> None:
    test_exclude_img_gen_namespace_chat()
    test_exclude_image_gen_namespace_chat()
    test_allow_aihorde_diffusion()
    test_allow_openrouter_flux()
    test_rank_prefers_icbinp_over_aibox()
    print("OK first_setup_image_gen_unit")


if __name__ == "__main__":
    main()
