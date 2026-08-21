"""Web search combo for Router Worker (not OmniRouter chat combos).

OmniRouter routes LLM completions only. Web search is a separate combo on
model-router: paid vendor first, local SearXNG last.
Default chain: tavily -> searxng.

Endpoints (mounted before the OpenAI proxy catch-all):
  POST /v1/search    { query, max_results?, backend? }
  POST /v1/extract   { url, backend? }
  GET  /v1/backends/next
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DEFAULT_CHAIN = ("tavily", "searxng")
EXTRACT_BACKENDS = ("tavily", "firecrawl")
SEARCH_RESULT_CAP = 10
SNIPPET_CHARS = 500

_raw_chain = os.environ.get("WEB_BACKENDS")
if _raw_chain is None:
    BACKENDS: list[str] = list(DEFAULT_CHAIN)
else:
    BACKENDS = [b.strip().lower() for b in _raw_chain.split(",") if b.strip()]
SEARCH_MAX = int(os.environ.get("WEB_SEARCH_MAX_RESULTS", "3"))
SEARXNG_URL = (os.environ.get("SEARXNG_URL") or "").rstrip("/")
SEARXNG_MAX = int(os.environ.get("SEARXNG_MAX_RESULTS", str(SEARCH_MAX)))
MESSAGES_PATH = Path(
    os.environ.get(
        "WEB_SEARCH_MESSAGES",
        str(Path(__file__).resolve().parent / "messages" / "ops-alerts.json"),
    )
)

router = APIRouter()


class SearchReq(BaseModel):
    query: str
    max_results: int = SEARCH_MAX
    backend: Optional[str] = None


class ExtractReq(BaseModel):
    url: str
    backend: Optional[str] = None


def _msg(key: str, fallback: str) -> str:
    try:
        data = json.loads(MESSAGES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback
    val = data.get(key) if isinstance(data, dict) else None
    if isinstance(val, dict):
        val = val.get("en") or val.get("default")
    return str(val or fallback)


def _key(name: str) -> str:
    return os.environ.get(f"{name.upper()}_API_KEY", "").strip()


def search_order(preferred: Optional[str] = None) -> list[str]:
    """Combo order; SearXNG stays last when configured."""
    order = [b for b in BACKENDS if b != "searxng"]
    if SEARXNG_URL and "searxng" in (BACKENDS or DEFAULT_CHAIN):
        order.append("searxng")
    elif SEARXNG_URL and not BACKENDS:
        order.append("searxng")
    if preferred:
        p = preferred.strip().lower()
        order = [p] + [b for b in order if b != p]
    return order


def health_fields() -> dict[str, Any]:
    return {
        "web_backends": search_order(),
        "web_keys": {name: bool(_key(name)) for name in ("tavily", "firecrawl", "exa")},
        "searxng": bool(SEARXNG_URL),
    }


async def _tavily_search(query: str, max_results: int) -> dict[str, Any]:
    key = _key("tavily")
    if not key:
        raise HTTPException(503, "TAVILY_API_KEY missing")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "max_results": max_results,
                "include_answer": True,
            },
        )
        r.raise_for_status()
        data = r.json()
    return {"backend": "tavily", "answer": data.get("answer"), "results": data.get("results", [])}


async def _firecrawl_search(query: str, max_results: int) -> dict[str, Any]:
    key = _key("firecrawl")
    if not key:
        raise HTTPException(503, "FIRECRAWL_API_KEY missing")
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            "https://api.firecrawl.dev/v1/search",
            headers={"Authorization": f"Bearer {key}"},
            json={"query": query, "limit": max_results},
        )
        r.raise_for_status()
        data = r.json()
    return {"backend": "firecrawl", "results": data.get("data") or data.get("results") or []}


async def _exa_search(query: str, max_results: int) -> dict[str, Any]:
    key = _key("exa")
    if not key:
        raise HTTPException(503, "EXA_API_KEY missing")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": key, "Content-Type": "application/json"},
            json={"query": query, "numResults": max_results, "type": "auto"},
        )
        r.raise_for_status()
        data = r.json()
    return {"backend": "exa", "results": data.get("results", [])}


async def _searxng_search(query: str, max_results: int) -> dict[str, Any]:
    if not SEARXNG_URL:
        raise HTTPException(503, "SEARXNG_URL missing")
    n = max(1, min(int(max_results or SEARXNG_MAX), SEARXNG_MAX, SEARCH_RESULT_CAP))
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        # Do not pass language=all — some engines return empty for that token.
        r = await client.get(
            f"{SEARXNG_URL}/search",
            params={"q": query, "format": "json"},
            headers={"User-Agent": "hermes-router-worker/websearch"},
        )
        r.raise_for_status()
        data = r.json()
    results = []
    for item in (data.get("results") or [])[:n]:
        results.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or item.get("link") or "",
                "content": (item.get("content") or item.get("snippet") or "")[:SNIPPET_CHARS],
                "engine": item.get("engine") or "",
            }
        )
    if not results:
        unresp = data.get("unresponsive_engines") or []
        hint = ""
        if unresp:
            # Keep short: [['brave','CAPTCHA'], ...]
            parts = []
            for row in unresp[:4]:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    parts.append(f"{row[0]}:{row[1]}")
                else:
                    parts.append(str(row))
            hint = f" unresponsive={{{', '.join(parts)}}}"
        raise RuntimeError(f"searxng returned no results{hint}")
    return {"backend": "searxng", "results": results, "answer": None}


async def _tavily_extract(url: str) -> dict[str, Any]:
    key = _key("tavily")
    if not key:
        raise HTTPException(503, "TAVILY_API_KEY missing")
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            "https://api.tavily.com/extract",
            json={"api_key": key, "urls": [url]},
        )
        r.raise_for_status()
        return {"backend": "tavily", "data": r.json()}


async def _firecrawl_extract(url: str) -> dict[str, Any]:
    key = _key("firecrawl")
    if not key:
        raise HTTPException(503, "FIRECRAWL_API_KEY missing")
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {key}"},
            json={"url": url, "formats": ["markdown"]},
        )
        r.raise_for_status()
        return {"backend": "firecrawl", "data": r.json()}


async def _run_backend(name: str, query: str, n: int) -> dict[str, Any]:
    match name:
        case "tavily":
            return await _tavily_search(query, n)
        case "firecrawl":
            return await _firecrawl_search(query, n)
        case "exa":
            return await _exa_search(query, n)
        case "searxng":
            return await _searxng_search(query, n)
        case _:
            raise RuntimeError(f"unknown backend {name}")


@router.get("/v1/backends/next")
def backends_next() -> dict[str, str]:
    order = search_order()
    return {"backend": order[0] if order else ""}


@router.post("/v1/search")
async def search(req: SearchReq) -> dict[str, Any]:
    order = search_order(req.backend)
    if not order:
        raise HTTPException(
            503,
            _msg("web_search_disabled", "Web search is unavailable (no search backends configured)."),
        )
    n = max(1, min(int(req.max_results or SEARCH_MAX), SEARCH_RESULT_CAP))
    errors: list[str] = []
    merged: list[Any] = []
    answer: Any = None
    used: list[str] = []
    for backend in order:
        try:
            hit = await _run_backend(backend, req.query, n)
        except Exception as e:  # noqa: BLE001 — try the next combo member
            errors.append(f"{backend}: {e}")
            continue
        used.append(str(hit.get("backend") or backend))
        if answer is None and hit.get("answer"):
            answer = hit.get("answer")
        rows = hit.get("results") if isinstance(hit.get("results"), list) else []
        for row in rows:
            if len(merged) >= n:
                break
            merged.append(row)
        if len(merged) >= n:
            break
    if merged or answer is not None:
        return {
            "backend": "+".join(used) if used else "combo",
            "answer": answer,
            "results": merged[:n],
            "errors": errors or None,
        }
    raise HTTPException(502, {"error": "all backends failed", "detail": errors})


@router.post("/v1/extract")
async def extract(req: ExtractReq) -> dict[str, Any]:
    order = [b for b in search_order(req.backend) if b in EXTRACT_BACKENDS]
    if not order:
        raise HTTPException(503, "web extract unavailable (no extract backend configured)")
    errors: list[str] = []
    for backend in order:
        try:
            if backend == "tavily":
                return await _tavily_extract(req.url)
            return await _firecrawl_extract(req.url)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{backend}: {e}")
            continue
    raise HTTPException(502, {"error": "all extract backends failed", "detail": errors})
