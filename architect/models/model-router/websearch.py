"""Web search combo for Router Worker.

Skill path: Hermes web-search skill → POST model-router /v1/search.
Combo order is config/env only (OmniRouter-style failover) — not hardcoded
in Python. Default file: config/web-search-combo.json (tavily → searxng).
Override: WEB_BACKENDS / WEB_EXTRACT_BACKENDS.

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

ROOT = Path(__file__).resolve().parent
COMBO_PATH = Path(
    os.environ.get(
        "WEB_SEARCH_COMBO_PATH",
        str(ROOT / "config" / "web-search-combo.json"),
    )
)
MESSAGES_PATH = Path(
    os.environ.get(
        "WEB_SEARCH_MESSAGES",
        str(ROOT / "messages" / "ops-alerts.json"),
    )
)
SEARCH_RESULT_CAP = 10
SNIPPET_CHARS = 500

# Known adapters only — membership registry, not failover order.
_ADAPTERS = frozenset({"tavily", "firecrawl", "exa", "searxng"})
_EXTRACT_ADAPTERS = frozenset({"tavily", "firecrawl"})

router = APIRouter()


def _load_combo() -> dict[str, Any]:
    try:
        data = json.loads(COMBO_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _split_csv(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [b.strip().lower() for b in raw.split(",") if b.strip()]


def _combo_backends() -> list[str]:
    """Failover order from WEB_BACKENDS env, else web-search-combo.json."""
    env = os.environ.get("WEB_BACKENDS")
    if env is not None:
        # Explicit empty → search off (operator cleared the combo).
        return _split_csv(env)
    cfg = _load_combo()
    raw = cfg.get("backends") if isinstance(cfg.get("backends"), list) else []
    out: list[str] = []
    for item in raw:
        name = str(item or "").strip().lower()
        if name and name not in out:
            out.append(name)
    return out


def _combo_extract() -> list[str]:
    env = os.environ.get("WEB_EXTRACT_BACKENDS")
    if env is not None:
        return [b for b in _split_csv(env) if b in _EXTRACT_ADAPTERS]
    cfg = _load_combo()
    raw = cfg.get("extract_backends") if isinstance(cfg.get("extract_backends"), list) else []
    out: list[str] = []
    for item in raw:
        name = str(item or "").strip().lower()
        if name in _EXTRACT_ADAPTERS and name not in out:
            out.append(name)
    return out


def _combo_max_results() -> int:
    try:
        return int(os.environ.get("WEB_SEARCH_MAX_RESULTS") or 0) or int(
            _load_combo().get("max_results") or 3
        )
    except (TypeError, ValueError):
        return 3


def _searxng_url() -> str:
    return (os.environ.get("SEARXNG_URL") or "").rstrip("/")


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
    """Config/env failover order. Skip searxng when SEARXNG_URL is unset."""
    order: list[str] = []
    for name in _combo_backends():
        if name not in _ADAPTERS:
            continue
        if name == "searxng" and not _searxng_url():
            continue
        if name not in order:
            order.append(name)
    if preferred:
        p = preferred.strip().lower()
        if p in _ADAPTERS and (p != "searxng" or _searxng_url()):
            order = [p] + [b for b in order if b != p]
    return order


def health_fields() -> dict[str, Any]:
    cfg = _load_combo()
    return {
        "web_combo": str(cfg.get("combo") or "websearch"),
        "web_backends": search_order(),
        "web_extract_backends": _combo_extract(),
        "web_keys": {name: bool(_key(name)) for name in ("tavily", "firecrawl", "exa")},
        "searxng": bool(_searxng_url()),
        "web_combo_path": str(COMBO_PATH),
    }


class SearchReq(BaseModel):
    query: str
    max_results: int = 0
    backend: Optional[str] = None


class ExtractReq(BaseModel):
    url: str
    backend: Optional[str] = None


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
    base = _searxng_url()
    if not base:
        raise HTTPException(503, "SEARXNG_URL missing")
    n = max(1, min(int(max_results or _combo_max_results()), SEARCH_RESULT_CAP))
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        r = await client.get(
            f"{base}/search",
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
    cfg = _load_combo()
    return {
        "combo": str(cfg.get("combo") or "websearch"),
        "backend": order[0] if order else "",
        "order": ",".join(order),
    }


@router.post("/v1/search")
async def search(req: SearchReq) -> dict[str, Any]:
    order = search_order(req.backend)
    if not order:
        raise HTTPException(
            503,
            _msg("web_search_disabled", "Web search is unavailable (no search backends configured)."),
        )
    n = max(1, min(int(req.max_results or _combo_max_results()), SEARCH_RESULT_CAP))
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
            "combo": str(_load_combo().get("combo") or "websearch"),
            "backend": "+".join(used) if used else "combo",
            "answer": answer,
            "results": merged[:n],
            "errors": errors or None,
        }
    raise HTTPException(502, {"error": "all backends failed", "detail": errors})


@router.post("/v1/extract")
async def extract(req: ExtractReq) -> dict[str, Any]:
    base = _combo_extract()
    if req.backend:
        p = req.backend.strip().lower()
        order = (
            [p] + [b for b in base if b != p]
            if p in _EXTRACT_ADAPTERS
            else list(base)
        )
    else:
        order = list(base)
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
