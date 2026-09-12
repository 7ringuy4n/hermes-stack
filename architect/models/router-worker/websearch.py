"""Web search for Router Worker (Hermes-facing).

Skill path: Hermes web-search → POST router-worker /v1/search → OmniRoute
``POST /v1/search`` with combo ``web-search`` (operator-owned members + failover in Omni UI).

Endpoints (mounted before the OpenAI proxy catch-all):
  POST /v1/search    { query, max_results? }
  POST /v1/extract   { url, backend? }
  GET  /v1/backends/next
"""
from __future__ import annotations

import json
import os
import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

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

_EXTRACT_ADAPTERS = frozenset({"tavily", "firecrawl", "direct"})
_DIRECT_EXTRACT_MAX_BYTES = 2 * 1024 * 1024
_DIRECT_EXTRACT_MAX_CHARS = 80_000

router = APIRouter()


def _web_search_combo_name() -> str:
    """Omni/Router combo name (operator-owned in Omni UI)."""
    for key in (
        "ROUTER_WORKER_WEB_SEARCH_COMBO",
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


def _combo_extract() -> list[str]:
    # Credentialed extractors retain priority; the bounded direct reader keeps
    # public-page extraction available when those optional keys are absent.
    return ["tavily", "firecrawl", "direct"]


class _ReadableHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._ignored = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in {"script", "style", "noscript", "svg"}:
            self._ignored += 1
        elif name == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in {"script", "style", "noscript", "svg"} and self._ignored:
            self._ignored -= 1
        elif name == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._ignored:
            return
        value = data.strip()
        if not value:
            return
        self.parts.append(value)
        if self._in_title:
            self.title_parts.append(value)


def _html_text(body: str) -> tuple[str, str]:
    parser = _ReadableHTML()
    parser.feed(body)
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()
    return title[:500], text[:_DIRECT_EXTRACT_MAX_CHARS]


async def _validate_public_url(raw_url: str) -> str:
    parsed = urlparse((raw_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only absolute HTTP(S) URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in {80, 443}:
        raise ValueError("only standard HTTP(S) ports are allowed")
    infos = await asyncio.get_running_loop().getaddrinfo(
        parsed.hostname, port, type=socket.SOCK_STREAM
    )
    addresses = {row[4][0] for row in infos if row and row[4]}
    if not addresses:
        raise ValueError("URL host did not resolve")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("URL host resolves to a non-public address")
    return parsed.geturl()


async def _direct_extract(url: str) -> dict[str, Any]:
    current = await _validate_public_url(url)
    async with httpx.AsyncClient(
        timeout=_provider_timeout_s(), follow_redirects=False, trust_env=False
    ) as client:
        for _ in range(4):
            async with client.stream(
                "GET",
                current,
                headers={"User-Agent": "HermesStack/1.0 public-page-extractor"},
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location") or ""
                    if not location:
                        raise RuntimeError("redirect response omitted Location")
                    current = await _validate_public_url(urljoin(current, location))
                    continue
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "").lower()
                if not any(
                    allowed in content_type
                    for allowed in ("text/html", "text/plain", "application/xhtml+xml", "application/json")
                ):
                    raise RuntimeError("direct extractor only accepts textual content")
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > _DIRECT_EXTRACT_MAX_BYTES:
                        raise RuntimeError("direct extractor response exceeds size limit")
                    chunks.append(chunk)
                encoding = response.encoding or "utf-8"
                body = b"".join(chunks).decode(encoding, errors="replace")
                if "html" in content_type:
                    title, content = _html_text(body)
                else:
                    title, content = "", body[:_DIRECT_EXTRACT_MAX_CHARS]
                if not content.strip():
                    raise RuntimeError("direct extractor returned empty content")
                return {
                    "backend": "direct",
                    "data": {"url": current, "title": title, "content": content},
                }
        raise RuntimeError("direct extractor exceeded redirect limit")


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
        or ""
    ).strip()


def _omni_configured() -> bool:
    return bool(_omni_search_url() and _omni_api_key())


def _searxng_url() -> str:
    return (os.environ.get("FALLBACK_SEARXNG_URL") or "").strip().rstrip("/")


def search_order(preferred: Optional[str] = None) -> list[str]:
    """Omni combo first, then the explicitly configured local search fallback."""
    order: list[str] = []
    if _omni_configured():
        order.append("omni")
    if _searxng_url():
        order.append("searxng")
    if preferred:
        p = preferred.strip().lower()
        if p in {"", _web_search_combo_name()}:
            return order
        if p not in order:
            return []
        return [p] + [name for name in order if name != p]
    return order


def health_fields() -> dict[str, Any]:
    combo = _web_search_combo_name()
    return {
        "web_combo": combo,
        "omni_search_combo": combo,
        "web_backends": search_order(),
        "web_keys": {name: bool(_key(name)) for name in ("tavily", "firecrawl")},
        "omni_search": _omni_configured(),
        "fallback_searxng": bool(_searxng_url()),
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
    # Include model=combo so Omni UI Requested Model is populated (same as chat combos).
    body = {
        "query": query,
        "max_results": n,
        "combo": combo,
        "model": combo,
        "include_answer": True,
    }
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


async def _searxng_search(query: str, max_results: int) -> dict[str, Any]:
    base = _searxng_url()
    if not base:
        raise RuntimeError("SearXNG fallback is not configured")
    n = max(1, min(int(max_results or _combo_max_results()), SEARCH_RESULT_CAP))
    async with httpx.AsyncClient(timeout=_provider_timeout_s()) as client:
        response = await client.get(
            f"{base}/search",
            params={"q": query, "format": "json"},
        )
        response.raise_for_status()
        data = response.json()
    rows = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "content": (item.get("content") or "")[:SNIPPET_CHARS],
                "provider": "searxng",
            }
        )
        if len(rows) >= n:
            break
    answer = data.get("answer") or None
    if not rows:
        for item in data.get("infoboxes") or []:
            if not isinstance(item, dict):
                continue
            urls = item.get("urls") or []
            first_url = urls[0] if isinstance(urls, list) and urls else {}
            if not isinstance(first_url, dict):
                first_url = {}
            content = item.get("content") or item.get("infobox") or ""
            title = item.get("title") or first_url.get("title") or query
            url = first_url.get("url") or ""
            if not content and not url:
                continue
            rows.append(
                {
                    "title": title,
                    "url": url,
                    "content": str(content)[:SNIPPET_CHARS],
                    "provider": "searxng",
                }
            )
            if len(rows) >= n:
                break
    if not rows and answer:
        rows.append(
            {
                "title": query,
                "url": "",
                "content": str(answer)[:SNIPPET_CHARS],
                "provider": "searxng",
            }
        )
    if not rows:
        raise RuntimeError("SearXNG fallback returned no results")
    return {"backend": "searxng", "answer": answer, "results": rows}


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
    backend = combo if order and order[0] == "omni" else (order[0] if order else "")
    return {
        "combo": combo,
        "backend": backend,
        "order": ",".join(combo if name == "omni" else name for name in order),
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
    hit: dict[str, Any] | None = None
    errors: list[str] = []
    for backend in order:
        try:
            hit = (
                await _omni_search(req.query, n)
                if backend == "omni"
                else await _searxng_search(req.query, n)
            )
            break
        except Exception as exc:  # noqa: BLE001 - continue through explicit fallbacks
            errors.append(f"{backend}:{type(exc).__name__}")
    if hit is None:
        raise HTTPException(502, {"error": "search providers failed", "detail": errors})
    rows = hit.get("results") if isinstance(hit.get("results"), list) else []
    return {
        "combo": combo if str(hit.get("backend")) != "searxng" else "",
        "backend": hit.get("backend") or combo,
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
            if backend == "firecrawl":
                return await _firecrawl_extract(req.url)
            return await _direct_extract(req.url)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{backend}: {e}")
            continue
    raise HTTPException(502, {"error": "all extract backends failed", "detail": errors})
