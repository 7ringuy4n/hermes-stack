#!/usr/bin/env python3
"""Unit: endpoint-aware model-router provider fallbacks."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))

from fallback_providers import (  # noqa: E402
    capability_for_path,
    configured_fallbacks,
    endpoint_failure_allows_fallback,
    replace_multipart_model,
)


def main() -> int:
    assert capability_for_path("v1/chat/completions") == "chat"
    assert capability_for_path("v1/chat/completions", has_vision=True) == "vision"
    assert capability_for_path("v1/embeddings") == "embedding"
    assert capability_for_path("v1/images/generations") == "image-gen"
    assert capability_for_path("v1/images/edits") == "image-edit"
    env = {
        "MODEL_ROUTER_FALLBACK_PROVIDER_ORDER": "deepseek,qwen,deepseek",
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
    assert endpoint_failure_allows_fallback(
        400, b'No images-capable targets in combo "image-gen"', "image-gen"
    )
    assert not endpoint_failure_allows_fallback(400, b"invalid prompt", "image-gen")
    print("OK model-router endpoint-aware fallbacks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
