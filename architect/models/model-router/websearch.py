"""Web search for Router Worker (Hermes-facing).

Skill path: Hermes web-search → POST model-router /v1/search → OmniRoute
``POST /v1/search`` with combo ``web-search`` (operator-owned members + failover in Omni UI).

Endpoints (mounted before the OpenAI proxy catch-all):
  POST /v1/search    { query, max_results? }
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


def _omni_configured() -> bool:
    return bool(_omni_search_url() and _omni_api_key())


def search_order(preferred: Optional[str] = None) -> list[str]:
    """Omni combo only when OMNIROUTER_* is configured."""
    if not _omni_configured():
        return []
    if preferred:
        p = preferred.strip().lower()
        if p not in {"", "omni", _web_search_combo_name()}:
            return []
    return ["omni"]


def health_fields() -> dict[str, Any]:
    combo = _web_search_combo_name()
    return {
        "web_combo": combo,
        "omni_search_combo": combo,
        "web_backends": search_order(),
        "web_extract_backends": _combo_extract(),
        "web_keys": {name: bool(_key(name)) for name in ("tavily", "firecrawl")},
        "omni_search": _omni_configured(),
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


@router.get("/v1/backends/next")
def backends_next() -> dict[str, str]:
    order = search_order()
    combo = _web_search_combo_name()
    return {
        "combo": combo,
        "backend": combo if order else "",
        "order": combo if order else "",
    }


@router.post("/v1/search")
async def search(req: SearchReq) -> dict[str, Any]:
    order = search_order(req.backend)
    if not order:
        raise HTTPException(
            503,
            _msg("web_search_disabled", "Web search is unavailable (Omni combo not configured)."),
        )
    n = max(1, min(int(req.max_results or _combo_max_results()), SEARCH_RESULT_CAP))
    combo = _web_search_combo_name()
    try:
        hit = await _omni_search(req.query, n)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 — surface Omni failure to caller
        raise HTTPException(502, {"error": "omni search failed", "detail": str(e)}) from e
    rows = hit.get("results") if isinstance(hit.get("results"), list) else []
    return {
        "combo": combo,
        "backend": combo,
        "answer": hit.get("answer"),
        "results": rows[:n],
    }


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
