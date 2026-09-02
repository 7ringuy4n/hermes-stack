#!/usr/bin/env python3
"""Unit tests for image-gen combo member selection (first-setup-omnirouter)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "first_setup_omnirouter",
    ROOT / "scripts" / "main" / "first-setup-omnirouter.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def _row(mid: str, **extra) -> dict:
    row = {"id": mid, "capabilities": {}}
    row.update(extra)
    return row


def test_image_output_from_catalog_type() -> None:
    assert mod._is_image_output_model(_row("pollinations/flux", type="image")) is True
    assert mod._is_image_output_model(_row("aihorde/ICBINP", output_modalities=["image"])) is True
    assert mod._is_image_output_model(_row("oc/big-pickle")) is False
    assert mod._is_image_output_model(_row("image-gen")) is False


def test_pollinations_flux_head() -> None:
    assert mod._is_pollinations_flux_model_id("pollinations/flux") is True
    assert mod._is_pollinations_flux_model_id("pollinations/flux-2-flex") is True
    assert mod._is_pollinations_flux_model_id("pollinations/chigwell/gpt-5.4") is False


def test_rank_prefers_pollinations_flux() -> None:
    horde = "aihorde/ICBINP"
    flux = "pollinations/flux"
    assert mod._rank_image_gen_model(flux) < mod._rank_image_gen_model(horde)


def test_resolve_image_gen_head_pollinations() -> None:
    ids = ["aihorde/ICBINP", "pollinations/flux", "img-gen/qwen-image-3.0-pro"]
    assert mod._resolve_image_gen_head(ids, {}) == "pollinations/flux"
    assert mod._resolve_image_gen_head(ids, {"IMAGE_GEN_HEAD_MEMBER": "aihorde/ICBINP"}) == "pollinations/flux"
    assert mod._order_image_gen_combo_members(ids, "pollinations/flux")[0] == "pollinations/flux"


def test_image_gen_combo_strategy_is_priority() -> None:
    assert mod.IMAGE_GEN_COMBO_STRATEGY == "priority"
    assert mod.VISION_OCR_COMBO_STRATEGY == "priority"
    assert mod.COMBO_STRATEGY == "round-robin"
    assert mod.IMAGE_GEN_COMBO_STRATEGY != mod.COMBO_STRATEGY
    assert mod.VISION_OCR_COMBO_STRATEGY != mod.COMBO_STRATEGY


def test_put_or_create_combo_strategy_only_keeps_members() -> None:
    original_http = getattr(mod, "http_json", None)
    captured = {}

    def fake_http(opener, method, url, body=None, timeout=25):
        if url.endswith("/api/combos") and method == "GET":
            return 200, {
                "combos": [
                    {
                        "id": "v1",
                        "name": "vision-ocr",
                        "strategy": "round-robin",
                        "models": [
                            {"model": "oc/mimo-v2.5-free", "priority": 1},
                            {"model": "oc/big-pickle", "priority": 2},
                        ],
                    }
                ]
            }
        captured["method"] = method
        captured["body"] = body
        return 200, {"id": "v1"}

    mod.http_json = fake_http
    try:
        mod._put_or_create_combo(
            object(),
            name="vision-ocr",
            description="vision",
            model_ids=["oc/big-pickle", "oc/mimo-v2.5-free"],
            force=False,
            strategy="priority",
        )
    finally:
        if original_http is not None:
            mod.http_json = original_http
        else:
            del mod.http_json
    assert captured.get("method") == "PUT"
    assert captured.get("body", {}).get("strategy") == "priority"
    models = [m["model"] for m in captured["body"]["models"]]
    assert models == ["oc/mimo-v2.5-free", "oc/big-pickle"]


def test_put_or_create_combo_uses_want_strategy() -> None:
    original_http = getattr(mod, "http_json", None)
    captured = {}

    def fake_http(opener, method, url, body=None, timeout=25):
        if url.endswith("/api/combos") and method == "GET":
            return 200, {"combos": []}
        captured["method"] = method
        captured["body"] = body
        return 201, {"id": "c1"}

    mod.http_json = fake_http
    try:
        mod._put_or_create_combo(
            object(),
            name="image-gen",
            description="diffusion only",
            model_ids=["pollinations/flux", "aihorde/ICBINP"],
            force=True,
            strategy="priority",
        )
    finally:
        if original_http is not None:
            mod.http_json = original_http
        else:
            del mod.http_json
    assert captured.get("method") == "POST"
    assert captured.get("body", {}).get("strategy") == "priority"
    assert captured["body"]["models"][0]["model"] == "pollinations/flux"


def main() -> None:
    test_image_output_from_catalog_type()
    test_pollinations_flux_head()
    test_rank_prefers_pollinations_flux()
    test_resolve_image_gen_head_pollinations()
    test_image_gen_combo_strategy_is_priority()
    test_put_or_create_combo_strategy_only_keeps_members()
    test_put_or_create_combo_uses_want_strategy()
    print("OK first_setup_image_gen_unit")


if __name__ == "__main__":
    main()
