"""Web search for Router Worker (Hermes-facing).

Skill path: Hermes web-search → POST model-router /v1/search.
**Default:** backend ``omni`` proxies to OmniRoute ``POST /v1/search`` with combo
``web-search`` only (operator-owned members + failover in Omni UI).

Direct ``tavily`` / ``firecrawl`` / ``searxng`` adapters remain for lab fallback
when ``WEB_BACKENDS`` lists them explicitly.

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

MESSAGES_PATH = Path(
    os.environ.get(
        "WEB_SEARCH_MESSAGES",
        str(ROOT / "messages" / "ops-alerts.json"),
    )
)
SEARCH_RESULT_CAP = 10
SNIPPET_CHARS = 500

# Known adapters only — membership registry, not failover order.
_ADAPTERS = frozenset({"omni", "tavily", "firecrawl", "exa", "searxng"})
_EXTRACT_ADAPTERS = frozenset({"tavily", "firecrawl"})

router = APIRouter()


def _web_search_combo_name() -> str:
    """Omni/Router combo name (operator-owned in Omni UI)."""
    for key in (
        "MODEL_ROUTER_WEB_SEARCH_COMBO",
        "WEB_SEARCH_COMBO",
        "OMNIROUTER_WEB_SEARCH_COMBO",
    ):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            return raw
    return "web-search"


def _env_timeout(name: str, default: float, lo: float = 3.0, hi: float = 90.0) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(lo, min(hi, float(raw)))
    except ValueError:
        return default


def _provider_timeout_s() -> float:
    """Per-request HTTP timeout for Omni combo search."""
    return _env_timeout("WEB_SEARCH_PROVIDER_TIMEOUT_S", 20.0, 5.0, 45.0)


def _split_csv(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [b.strip().lower() for b in raw.split(",") if b.strip()]


def _combo_backends() -> list[str]:
    """Failover order: WEB_BACKENDS env, else Omni combo-only when configured."""
    env = os.environ.get("WEB_BACKENDS")
    if env is not None:
        return _split_csv(env)
    if _omni_search_url() and _omni_api_key():
        return ["omni"]
    return []


def _combo_extract() -> list[str]:
    env = os.environ.get("WEB_EXTRACT_BACKENDS")
    if env is not None:
        return [b for b in _split_csv(env) if b in _EXTRACT_ADAPTERS]
    return ["tavily", "firecrawl"]


def _combo_max_results() -> int:
    try:
        raw = (os.environ.get("WEB_SEARCH_MAX_RESULTS") or "").strip()
        n = int(raw) if raw else 3
        return max(1, min(n, SEARCH_RESULT_CAP))
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


def _omni_search_url() -> str:
    """Omni OpenAI-compat base ends with /v1 → POST …/v1/search."""
    base = (os.environ.get("OMNIROUTER_BASE_URL") or "").rstrip("/")
    if not base:
        return ""
    return f"{base}/search"


def _omni_api_key() -> str:
    return (
        os.environ.get("OMNIROUTER_API_KEY")
        or os.environ.get("N9ROUTER_API_KEY")
        or ""
    ).strip()


def search_order(preferred: Optional[str] = None) -> list[str]:
    """Env/default failover order. Skip adapters that lack required env."""
    order: list[str] = []
    for name in _combo_backends():
        if name not in _ADAPTERS:
            continue
        if name == "searxng" and not _searxng_url():
            continue
        if name == "omni" and (not _omni_search_url() or not _omni_api_key()):
            continue
        if name not in order:
            order.append(name)
    if preferred:
        p = preferred.strip().lower()
        ok = p in _ADAPTERS
        if p == "searxng" and not _searxng_url():
            ok = False
        if p == "omni" and (not _omni_search_url() or not _omni_api_key()):
            ok = False
        if ok:
            order = [p] + [b for b in order if b != p]
    return order


def health_fields() -> dict[str, Any]:
    return {
        "web_combo": _web_search_combo_name(),
        "omni_search_combo": _web_search_combo_name(),
        "web_backends": search_order(),
        "web_extract_backends": _combo_extract(),
        "web_keys": {name: bool(_key(name)) for name in ("tavily", "firecrawl", "exa")},
        "searxng": bool(_searxng_url()),
        "omni_search": bool(_omni_search_url() and _omni_api_key()),
    }


class SearchReq(BaseModel):
    query: str
    max_results: int = 0
    backend: Optional[str] = None


class ExtractReq(BaseModel):
    url: str
    backend: Optional[str] = None


def _normalize_omni_search_hit(data: dict[str, Any], combo: str) -> dict[str, Any] | None:
    results: list[dict[str, Any]] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or item.get("link") or "",
                "content": (
                    item.get("content")
                    or item.get("snippet")
                    or item.get("description")
                    or ""
                )[:SNIPPET_CHARS],
                "provider": combo,
            }
        )
    if results or data.get("answer"):
        return {
            "backend": combo,
            "answer": data.get("answer"),
            "results": results,
        }
    return None


async def _omni_search(query: str, max_results: int) -> dict[str, Any]:
    """Proxy to OmniRoute search gateway — combo name only (no provider bypass)."""
    url = _omni_search_url()
    key = _omni_api_key()
    if not url or not key:
        raise HTTPException(503, "Omni search unavailable (OMNIROUTER_BASE_URL / OMNIROUTER_API_KEY)")
    n = max(1, min(int(max_results or _combo_max_results()), SEARCH_RESULT_CAP))
    combo = _web_search_combo_name()
    body = {"query": query, "max_results": n, "combo": combo}
    per_timeout = _provider_timeout_s()
    async with httpx.AsyncClient(timeout=per_timeout) as client:
        r = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("omni search returned non-object response")
    hit = _normalize_omni_search_hit(data, combo)
    if hit:
        return hit
    raise RuntimeError(f"combo {combo} returned no results")


async def _tavily_search(query: str, max_results: int) -> dict[str, Any]:
    key = _key("tavily")
    if not key:
        raise HTTPException(503, "TAVILY_API_KEY missing")
    async with httpx.AsyncClient(timeout=_provider_timeout_s()) as client:
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
    timeout = min(30.0, max(_provider_timeout_s(), _env_timeout("WEB_SEARCH_FIRECRAWL_TIMEOUT_S", 25.0, 5.0, 45.0)))
    async with httpx.AsyncClient(timeout=timeout) as client:
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
    async with httpx.AsyncClient(timeout=_provider_timeout_s()) as client:
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
    timeout = min(_provider_timeout_s(), _env_timeout("WEB_SEARCH_SEARXNG_TIMEOUT_S", 15.0, 3.0, 30.0))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
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
        case "omni":
            return await _omni_search(query, n)
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
    return {
        "combo": _web_search_combo_name(),
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
        except Exception as e:  # noqa: BLE001 — try the next backend when env lists several
            errors.append(f"{backend}: {e}")
            continue
        label = str(hit.get("backend") or backend)
        used.append(label)
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
        combo = _web_search_combo_name()
        primary = combo if combo in used else ("+".join(used) if used else combo)
        return {
            "combo": combo,
            "backend": primary,
            "answer": answer,
            "results": merged[:n],
            "errors": errors or None,
        }
    raise HTTPException(502, {"error": "all backends failed", "detail": errors})


@router.get("/v1/searxng-compat/search")
async def searxng_compat_search(q: str = "", format: str = "json") -> dict[str, Any]:
    """SearXNG-shaped GET shim for Hermes native ``web_search`` (toolset web)."""
    if (format or "").lower() not in {"", "json"}:
        raise HTTPException(400, "only format=json is supported")
    query = (q or "").strip()
    if not query:
        raise HTTPException(400, "q is required")
    body = await search(SearchReq(query=query, max_results=_combo_max_results()))
    results = []
    for i, row in enumerate(body.get("results") or []):
        if not isinstance(row, dict):
            continue
        results.append(
            {
                "url": row.get("url") or "",
                "title": row.get("title") or "",
                "content": row.get("content") or row.get("snippet") or "",
                "engine": str(body.get("backend") or body.get("combo") or "web-search"),
                "score": max(0.0, 1.0 - (i * 0.05)),
                "category": "general",
            }
        )
    return {
        "query": query,
        "number_of_results": len(results),
        "results": results,
        "answers": [],
        "corrections": [],
        "infoboxes": [],
        "suggestions": [],
        "unresponsive_engines": [],
    }


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
