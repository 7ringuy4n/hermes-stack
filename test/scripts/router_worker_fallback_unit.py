#!/usr/bin/env python3
"""Unit: endpoint-aware router-worker provider fallbacks."""
from __future__ import annotations

import os
import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "router-worker"))

from fallback_providers import (  # noqa: E402
    capability_for_path,
    configured_fallbacks,
    encode_proxy_body,
    endpoint_failure_allows_fallback,
    replace_multipart_model,
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    assert capability_for_path("v1/chat/completions") == "chat"
    assert capability_for_path("v1/chat/completions", has_vision=True) == "vision"
    assert capability_for_path("v1/embeddings") == "embedding"
    assert capability_for_path("v1/images/generations") == "image-gen"
    assert capability_for_path("v1/images/edits") == "image-edit"
    env = {
        "ROUTER_WORKER_FALLBACK_PROVIDER_ORDER": "deepseek,qwen,deepseek",
        "DEEPSEEK_API_BASE": "https://compat.example/v1",
        "DEEPSEEK_API_KEY": "redacted",
        "DEEPSEEK_CHAT_MODEL": "chat-model",
        "QWEN_API_BASE": "https://qwen.example/v1",
        "QWEN_API_KEY": "redacted",
        "QWEN_EMBEDDING_MODEL": "embed-model",
    }
    with patch.dict(os.environ, env, clear=True):
        assert configured_fallbacks("chat") == [
            ("deepseek", "https://compat.example/v1", "redacted", "chat-model")
        ]
        assert configured_fallbacks("embedding") == [
            ("qwen", "https://qwen.example/v1", "redacted", "embed-model")
        ]
        assert configured_fallbacks("image-edit") == []
    boundary = "unit-boundary"
    source = (
        b"--unit-boundary\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n"
        b"image-edit\r\n--unit-boundary\r\nContent-Disposition: form-data; "
        b"name=\"image\"; filename=\"source.png\"\r\n\r\n\x00image-edit\xff\r\n"
        b"--unit-boundary--\r\n"
    )
    replaced = replace_multipart_model(
        source, f"multipart/form-data; boundary={boundary}", "provider/edit-model"
    )
    assert b"\r\nprovider/edit-model\r\n" in replaced
    assert b"\x00image-edit\xff" in replaced
    assert encode_proxy_body(source, {"stream": False}, is_json_request=False) == source
    assert encode_proxy_body(source, {"stream": False}, is_json_request=True) == b'{"stream": false}'
    assert endpoint_failure_allows_fallback(
        400, b'No images-capable targets in combo "image-gen"', "image-gen"
    )
    assert not endpoint_failure_allows_fallback(400, b"invalid prompt", "image-gen")
    patcher = _load(ROOT / "scripts/main/patch-hermes-router-worker.py", "patch_router_web_unit")
    configured = patcher._patch_web_routing("model:\n  default: hermes\n")
    assert "search_backend: router-worker" in configured
    assert "extract_backend: router-worker" in configured
    assert patcher._patch_web_routing(configured) == configured

    common = types.ModuleType("plugins.web._common")
    common.BaseWebSearchProvider = object
    common.search_fail = lambda error: {"success": False, "error": error}
    common.search_ok = lambda rows: {"success": True, "results": rows}
    sys.modules.setdefault("httpx", types.ModuleType("httpx"))
    sys.modules["plugins"] = types.ModuleType("plugins")
    sys.modules["plugins.web"] = types.ModuleType("plugins.web")
    sys.modules["plugins.web._common"] = common
    provider = _load(
        ROOT / "hermes/main/plugins/web/router_worker/provider.py",
        "router_worker_web_provider_unit",
    )
    router_package = types.ModuleType("plugins.web.router_worker")
    sys.modules["plugins.web.router_worker"] = router_package
    sys.modules["plugins.web.router_worker.provider"] = provider
    plugin = _load(
        ROOT / "hermes/main/plugins/web/router_worker/__init__.py",
        "router_worker_web_plugin_unit",
    )

    class _PluginContext:
        registered = None

        def register_web_search_provider(self, value):
            self.registered = value

    plugin_context = _PluginContext()
    plugin.register(plugin_context)
    assert isinstance(plugin_context.registered, provider.RouterWorkerWebSearchProvider)
    tavily = provider._extract_item(
        "https://example.test/a",
        {"data": {"results": [{"url": "https://example.test/a", "title": "A", "raw_content": "Body A"}]}},
    )
    firecrawl = provider._extract_item(
        "https://example.test/b",
        {"data": {"data": {"markdown": "Body B", "metadata": {"title": "B"}}}},
    )
    assert tavily["content"] == "Body A" and tavily["title"] == "A"
    assert firecrawl["content"] == "Body B" and firecrawl["title"] == "B"
    direct = provider._extract_item(
        "https://example.test/c",
        {"data": {"url": "https://example.test/c", "title": "C", "content": "Body C"}},
    )
    assert direct["content"] == "Body C" and direct["title"] == "C"

    class _Router:
        def get(self, *_args, **_kwargs):
            return lambda fn: fn

        def post(self, *_args, **_kwargs):
            return lambda fn: fn

    fastapi = types.ModuleType("fastapi")
    fastapi.APIRouter = _Router
    fastapi.HTTPException = type("HTTPException", (Exception,), {})
    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = type("BaseModel", (), {})
    sys.modules["fastapi"] = fastapi
    sys.modules["pydantic"] = pydantic
    websearch = _load(
        ROOT / "architect/models/router-worker/websearch.py",
        "router_worker_websearch_unit",
    )
    assert websearch._combo_extract() == ["tavily", "firecrawl", "direct"]
    title, content = websearch._html_text(
        "<html><head><title>Example</title><style>hidden</style></head>"
        "<body><h1>Hello</h1><script>bad()</script><p>Public page</p></body></html>"
    )
    assert title == "Example"
    assert "Hello Public page" in content and "hidden" not in content and "bad()" not in content
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 80))]):
        try:
            asyncio.run(websearch._validate_public_url("http://internal.test"))
        except ValueError as exc:
            assert "non-public" in str(exc)
        else:
            raise AssertionError("private destination must be blocked")
    print("OK router-worker endpoint-aware fallbacks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
