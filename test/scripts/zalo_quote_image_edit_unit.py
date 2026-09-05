#!/usr/bin/env python3
"""Unit: a Zalo quoted image reaches the image-edit combo and yields one artifact."""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ZALO = ROOT / "hermes" / "main" / "plugins" / "zalo"
sys.path.insert(0, str(ZALO))

from attachment import merge_inbound_quote_media  # noqa: E402
from classify_client import plan_allows_image_edit, plan_media_shortcut_gate  # noqa: E402
from media_shortcuts import run_image_edit  # noqa: E402


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def main() -> int:
    quoted = {
        "msgType": "chat.photo",
        "media": {
            "url": "https://example.invalid/quoted.png",
            "fileName": "quoted.png",
            "kind": "image",
            "mime": "image/png",
        },
    }
    media, merged = merge_inbound_quote_media({"quoted": quoted}, None)
    assert media and media["url"].endswith("quoted.png")
    assert merged["media"]["kind"] == "image"

    plan = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "skill": "image-edit",
        "skill_action": "edit_media",
        "output_type": "image",
        "attachments_required": True,
        "attachment_types": ["image"],
    }
    assert plan_allows_image_edit(plan)
    assert plan_media_shortcut_gate(plan) == "image_edit"

    captured: dict[str, object] = {}
    edited = b"\x89PNG\r\n\x1a\n" + (b"edited" * 32)

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = bytes(request.data)
        captured["timeout"] = timeout
        return _Response({"data": [{"b64_json": base64.b64encode(edited).decode()}]})

    with tempfile.TemporaryDirectory() as root:
        source = Path(root) / "quoted.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\nsource")
        prior = dict(os.environ)
        try:
            os.environ["HERMES_SHARED_DATA"] = root
            os.environ["OMNIROUTER_API_KEY"] = "unit-secret"
            os.environ["OMNIROUTER_BASE_URL"] = "http://omni-router:20129/v1"
            os.environ["IMAGE_EDIT_COMBO"] = "image-edit"
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                result = run_image_edit(
                    "Keep the subject and change the background",
                    str(source),
                    "zalo-thread",
                    classified=True,
                )
        finally:
            os.environ.clear()
            os.environ.update(prior)
        assert result and result.get("ok") is True
        output = Path(str(result["file"]))
        assert output.read_bytes() == edited

    body = bytes(captured["body"])
    assert captured["url"] == "http://omni-router:20129/v1/images/edits"
    assert b'name="model"' in body and b"image-edit" in body
    assert b'name="prompt"' in body
    assert b'name="image"; filename="quoted.png"' in body
    adapter = (ZALO / "adapter.py").read_text(encoding="utf-8")
    assert "run_image_edit" in adapter
    assert "media_urls=list(event.media_urls or [])" in adapter
    print("OK zalo_quote_image_edit_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
