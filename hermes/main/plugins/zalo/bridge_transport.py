"""HTTP transport for the Zalo bridge.

This module owns wire concerns only: authentication headers, timeouts, JSON
decoding, and normalized transport errors. Conversation policy stays in the
platform adapter.
"""
from __future__ import annotations

import json
from typing import Any, Optional


class ZaloBridgeTransport:
    def __init__(self, base_url: str, token: str = "") -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.token = str(token or "")

    def headers(self, *, json_content: bool = True) -> dict[str, str]:
        headers: dict[str, str] = {}
        if json_content:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["x-bridge-token"] = self.token
        return headers

    async def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if not self.base_url:
            return {"error": "no bridge"}
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=120 if path == "/send-attachment" else 60)
        try:
            # Outbound calls intentionally do not share the long-lived SSE
            # session; doing so can disconnect the event stream under load.
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.base_url}{path}",
                    data=json.dumps(body),
                    headers=self.headers(),
                ) as response:
                    try:
                        data = await response.json(content_type=None)
                    except Exception:
                        try:
                            response_text = await response.text()
                        except Exception:
                            response_text = ""
                        return {"error": f"http {response.status}: {response_text[:180]}"}
                    if not isinstance(data, dict):
                        return {"error": f"http {response.status}: {str(data)[:160]}"}
                    if response.status >= 400:
                        data["error"] = str(
                            data.get("error") or data.get("message") or f"http {response.status}"
                        )
                    return data
        except Exception as exc:
            return {"error": str(exc)}

    async def get(
        self,
        session,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not session or session.closed or not self.base_url:
            return {"error": "no session"}
        import aiohttp
        try:
            async with session.get(
                f"{self.base_url}{path}",
                params=params or {},
                headers=self.headers(),
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                data = await response.json(content_type=None)
                return data if isinstance(data, dict) else {"error": str(data)[:160]}
        except Exception as exc:
            return {"error": str(exc)}
