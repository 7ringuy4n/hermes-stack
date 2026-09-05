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


def test_image_output_from_catalog_metadata() -> None:
    assert (
        mod._is_image_output_model(
            _row("provider-a/flux", type="image", supportedEndpoints=["images"])
        )
        is True
    )
    assert (
        mod._is_image_output_model(
            _row(
                "provider-b/diffusion",
                apiFormat="images-generations",
                supportedEndpoints=["images"],
            )
        )
        is True
    )
    assert (
        mod._is_image_output_model(
            _row("provider-c/model", supportedEndpoints=["chat"], capabilities={"image_generation": False})
        )
        is False
    )
    assert mod._is_image_output_model(_row("oc/big-pickle", supportedEndpoints=["chat"])) is False
    assert mod._is_image_output_model(_row("image-gen")) is False
    assert (
        mod._is_image_output_model(
            _row("provider-d/model", output_modalities=["image"], supportedEndpoints=["chat"])
        )
        is False
    )


def test_rank_prefers_images_generations_metadata() -> None:
    catalog = [
        _row(
            "provider-a/horde-model",
            supportedEndpoints=["images"],
            apiFormat="images-generations",
            provider="provider-a",
        ),
        _row(
            "provider-b/flux",
            type="image",
            supportedEndpoints=["images"],
            provider="provider-b",
        ),
    ]
    horde = "provider-a/horde-model"
    flux = "provider-b/flux"
    assert mod._rank_image_gen_model(horde, catalog) < mod._rank_image_gen_model(flux, catalog)


def test_connection_model_helpers() -> None:
    class _Opener:
        pass

    opener = _Opener()
    connections = [{"id": "c1", "provider": "node-chat-1"}]

    def fake_providers(op, method, url, body=None, timeout=25):
        if url.endswith("/api/providers") and method == "GET":
            return 200, {"connections": connections}
        if "/api/providers/c1/models" in url and method == "GET":
            return 200, {"models": [{"id": "wan2.7-image-pro"}, {"id": "qwen-image-2.0"}]}
        raise AssertionError(f"unexpected {method} {url}")

    orig = mod.http_json
    mod.http_json = fake_providers
    try:
        conn = mod._connection_for_provider_node(opener, "node-chat-1")
        assert conn and conn.get("id") == "c1"
        assert mod._connection_model_ids(opener, "c1") == ["wan2.7-image-pro", "qwen-image-2.0"]
    finally:
        mod.http_json = orig


def test_wired_custom_provider_image_ids() -> None:
    class _Opener:
        pass

    opener = _Opener()
    catalog_rows = [
        _row("ai-box/qwen-image-2.0", type="image"),
        _row("provider-b/flux", type="image", supportedEndpoints=["images"]),
    ]

    def fake_nodes(op):
        return [{"id": "openai-compatible-images-abc", "prefix": "ai-box", "apiType": "images-generations"}]

    def fake_prefix_node(op, prefix):
        if prefix == "ai-box":
            return "openai-compatible-images-abc"
        return ""

    def fake_custom(op, provider):
        if provider == "openai-compatible-images-abc":
            return {
                "qwen-image-2.0": {
                    "id": "qwen-image-2.0",
                    "supportedEndpoints": ["images"],
                    "apiFormat": "images-generations",
                }
            }
        return {}

    orig_nodes = mod._images_generations_provider_nodes
    orig_prefix = mod._prefix_resolved_provider_node_id
    orig_custom = mod._custom_models_by_provider
    mod._images_generations_provider_nodes = fake_nodes
    mod._prefix_resolved_provider_node_id = fake_prefix_node
    mod._custom_models_by_provider = fake_custom
    try:
        wired = mod._wired_custom_provider_image_ids(opener)
        assert wired == ["ai-box/qwen-image-2.0"]
        outside = mod._catalog_image_ids_outside_custom_providers(
            catalog_rows, {"ai-box"}
        )
        assert outside == ["provider-b/flux"]
    finally:
        mod._images_generations_provider_nodes = orig_nodes
        mod._prefix_resolved_provider_node_id = orig_prefix
        mod._custom_models_by_provider = orig_custom


def test_vision_trusts_catalog_capability_over_incomplete_modalities() -> None:
    kimi = {
        "fullModel": "ai-box/kimi-k3",
        "supportsVision": True,
        "supportedEndpoints": ["chat"],
        "modalities": ["text"],
        "provider": "ai-box",
    }
    kimi_code = {**kimi, "fullModel": "ai-box/kimi-k2.7-code"}
    capable = {
        "fullModel": "oc/mimo-v2.5-free",
        "supportsVision": True,
        "supportedEndpoints": ["chat"],
        "modalities": ["text", "image"],
        "capabilities": {"vision": True},
        "provider": "oc",
    }
    assert mod._is_vision_capable_model_row(kimi) is True
    assert mod._is_vision_capable_model_row(kimi_code) is True
    assert mod._is_vision_capable_model_row(capable) is True


def test_fallback_combo_strategy_constants() -> None:
    assert mod.FALLBACK_COMBO_STRATEGY == "priority"
    assert mod.CLASSIFIER_COMBO_STRATEGY == "priority"
    assert mod.EMBEDDING_COMBO_STRATEGY == "priority"
    assert mod.WEB_SEARCH_COMBO_STRATEGY == "priority"
    assert mod.IMAGE_GEN_COMBO_STRATEGY == "priority"
    assert mod.VISION_OCR_COMBO_STRATEGY == "priority"
    assert mod.HERMES_COMBO_STRATEGY == "priority"
    assert mod.COMBO_STRATEGY == "priority"


def test_image_gen_combo_strategy_is_priority() -> None:
    test_fallback_combo_strategy_constants()


def test_operator_media_shells_are_non_destructive() -> None:
    calls: list[dict] = []
    original = mod.ensure_opencode_combo

    def fake_ensure(opener, **kwargs):
        calls.append(kwargs)
        return kwargs["name"]

    mod.ensure_opencode_combo = fake_ensure
    try:
        mod.ensure_operator_media_shells(object(), setup_only=True)
    finally:
        mod.ensure_opencode_combo = original
    assert [row["name"] for row in calls] == ["image-edit", "video-gen", "video-edit"]
    assert all(row["setup_only"] is True for row in calls)
    assert all(row["strategy"] == "priority" for row in calls)
    assert all(row["enforce_strategy_only"] is True for row in calls)


def test_setup_only_strategy_migration_preserves_members() -> None:
    original_http = getattr(mod, "http_json", None)
    captured = {}

    def fake_http(opener, method, url, body=None, timeout=25):
        if url.endswith("/api/combos") and method == "GET":
            return 200, {
                "combos": [{
                    "id": "h1",
                    "name": "hermes",
                    "strategy": "round-robin",
                    "models": [
                        {"model": "oc/a", "priority": 1},
                        {"model": "oc/b", "priority": 2},
                    ],
                }]
            }
        captured["method"] = method
        captured["body"] = body
        return 200, {"id": "h1"}

    mod.http_json = fake_http
    try:
        mod.ensure_opencode_combo(
            object(),
            name="hermes",
            description="chat",
            strategy="priority",
            setup_only=True,
            enforce_strategy_only=True,
        )
    finally:
        if original_http is not None:
            mod.http_json = original_http
        else:
            del mod.http_json
    assert captured.get("method") == "PUT"
    assert captured["body"]["strategy"] == "priority"
    assert [row["model"] for row in captured["body"]["models"]] == ["oc/a", "oc/b"]


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
            model_ids=["provider-a/flux", "provider-b/horde"],
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
    assert captured["body"]["models"][0]["model"] == "provider-a/flux"


def test_web_search_member_order() -> None:
    original_http = getattr(mod, "http_json", None)

    def fake_http(opener, method, url, body=None, timeout=25):
        if url.endswith("/api/providers") and method == "GET":
            return 200, {
                "connections": [
                    {"provider": "searxng-search", "id": "s1", "isActive": True},
                    {"provider": "tavily-search", "id": "t1", "isActive": True},
                ]
            }
        raise AssertionError(f"unexpected {method} {url}")

    mod.http_json = fake_http
    try:
        members = mod.list_web_search_combo_members(object())
    finally:
        if original_http is not None:
            mod.http_json = original_http
        else:
            del mod.http_json
    assert members == ["tavily-search", "searxng-search"]


def main() -> None:
    test_image_output_from_catalog_metadata()
    test_rank_prefers_images_generations_metadata()
    test_connection_model_helpers()
    test_wired_custom_provider_image_ids()
    test_vision_trusts_catalog_capability_over_incomplete_modalities()
    test_image_gen_combo_strategy_is_priority()
    test_operator_media_shells_are_non_destructive()
    test_setup_only_strategy_migration_preserves_members()
    test_put_or_create_combo_strategy_only_keeps_members()
    test_web_search_member_order()
    test_put_or_create_combo_uses_want_strategy()
    print("OK first_setup_image_gen_unit")


if __name__ == "__main__":
    main()
