"""DeepSeek OCR helper — call via dispatcher or Hermes skill.

See https://deepseek-ocr.io/ — prefer API or local GPU; this stub documents the contract.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


async def ocr_image(path: str, *, prompt: str = "Analyze this file. Describe visible content and extract any readable text as markdown.") -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_OCR_API_KEY", "").strip()
    base = os.environ.get("DEEPSEEK_OCR_BASE_URL", "https://api.deepseek.com").rstrip("/")
    if not api_key:
        return {"ok": False, "error": "DEEPSEEK_OCR_API_KEY not set"}
    # OpenAI-compatible vision/OCR style request — adjust model id to your gateway
    model = os.environ.get("DEEPSEEK_OCR_MODEL", "deepseek-ocr")
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Placeholder: wire to your chosen DeepSeek OCR endpoint / 9Router route
        r = await client.post(
            f"{base}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "text", "text": f"local_file:{path}"},
                        ],
                    }
                ],
            },
        )
        if r.status_code >= 400:
            return {"ok": False, "status": r.status_code, "body": r.text[:500]}
        data = r.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "text": text, "raw": data}
