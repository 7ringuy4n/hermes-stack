"""Hermes native web provider routed through the stack Router Worker.

This keeps provider credentials in Router Worker/OpenBao while giving Hermes a
real extraction-capable backend instead of inheriting SearXNG for extraction.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import httpx

from plugins.web._common import BaseWebSearchProvider, search_fail, search_ok


def _base_url() -> str:
    return (os.environ.get("ROUTER_WORKER_WEB_URL") or "http://router-worker:8096").rstrip("/")


def _extract_item(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    direct_content = str(data.get("content") or "")
    if direct_content:
        return {
            "url": str(data.get("url") or url),
            "title": str(data.get("title") or ""),
            "content": direct_content,
            "raw_content": direct_content,
        }
    results = data.get("results") if isinstance(data.get("results"), list) else []
    first = results[0] if results and isinstance(results[0], dict) else {}
    if first:
        return {
            "url": str(first.get("url") or url),
            "title": str(first.get("title") or ""),
            "content": str(first.get("raw_content") or first.get("content") or ""),
            "raw_content": str(first.get("raw_content") or first.get("content") or ""),
        }
    fire_data = data.get("data") if isinstance(data.get("data"), dict) else data
    metadata = fire_data.get("metadata") if isinstance(fire_data.get("metadata"), dict) else {}
    content = str(fire_data.get("markdown") or fire_data.get("html") or fire_data.get("content") or "")
    if content:
        return {
            "url": str(metadata.get("sourceURL") or metadata.get("url") or url),
            "title": str(metadata.get("title") or ""),
            "content": content,
            "raw_content": content,
        }
    return {"url": url, "title": "", "content": "", "error": "Router Worker extract returned no content"}


class RouterWorkerWebSearchProvider(BaseWebSearchProvider):
    NAME = "router-worker"
    DISPLAY_NAME = "Router Worker"
    EXTRACT = True

    def is_available(self) -> bool:
        return bool(_base_url())

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        try:
            response = httpx.post(
                f"{_base_url()}/v1/search",
                json={"query": query, "max_results": max(1, min(int(limit), 10))},
                timeout=45.0,
            )
            response.raise_for_status()
            payload = response.json()
            rows = []
            for item in payload.get("results") or []:
                if not isinstance(item, dict):
                    continue
                rows.append({
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("url") or ""),
                    "content": str(item.get("content") or item.get("snippet") or ""),
                })
            return search_ok(rows) if rows else search_fail("Router Worker search returned no results")
        except Exception as exc:  # noqa: BLE001 - provider envelope owns the failure
            return search_fail(f"Router Worker search failed: {type(exc).__name__}")

    async def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        results: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=130.0) as client:
            for url in urls:
                try:
                    response = await client.post(f"{_base_url()}/v1/extract", json={"url": url})
                    response.raise_for_status()
                    results.append(_extract_item(url, response.json()))
                except Exception as exc:  # noqa: BLE001 - preserve per-URL result order
                    results.append({"url": url, "title": "", "content": "", "error": type(exc).__name__})
        return results
