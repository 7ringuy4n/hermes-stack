"""
API Gateway — VPN/LAN HTTP entry with shared Valkey rate limiting.

Zalo bridge/proxy must NOT hairpin through this service.
Coding skill paths skip rate-limit (product MUST).
Admin-editable messages: messages/en.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import redis
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# ── constants (env-overridable) ─────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
UPSTREAM_URL = os.environ.get(
    "GATEWAY_UPSTREAM_URL", "http://traefik:80"
).rstrip("/")
LISTEN_PORT = int(os.environ.get("GATEWAY_PORT", "8088"))
RATE_LIMIT_REQUESTS = int(os.environ.get("GATEWAY_RATE_LIMIT_REQUESTS", "60"))
RATE_LIMIT_WINDOW_S = int(os.environ.get("GATEWAY_RATE_LIMIT_WINDOW_S", "60"))
RATE_KEY_PREFIX = os.environ.get("GATEWAY_RATE_KEY_PREFIX", "rate:gw")
# Comma-separated path prefixes that skip RL (coding skills — no rate-limit)
SKIP_RL_PATH_PREFIXES = tuple(
    p.strip()
    for p in os.environ.get(
        "GATEWAY_SKIP_RL_PATHS", "/coding,/v1/coding,/skills/coding"
    ).split(",")
    if p.strip()
)
SKIP_RL_HEADER = os.environ.get("GATEWAY_SKIP_RL_HEADER", "x-assistant-skill")
SKIP_RL_HEADER_VALUES = {
    v.strip().lower()
    for v in os.environ.get("GATEWAY_SKIP_RL_HEADER_VALUES", "coding").split(",")
    if v.strip()
}
MESSAGES_PATH = Path(
    os.environ.get(
        "GATEWAY_MESSAGES_FILE",
        str(Path(__file__).resolve().parent / "messages" / "en.json"),
    )
)
PROXY_TIMEOUT_S = float(os.environ.get("GATEWAY_PROXY_TIMEOUT_S", "120"))

app = FastAPI(title="hermes-stack-api-gateway", version="0.1.0")
_redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
_http: httpx.AsyncClient | None = None


def _load_messages() -> dict:
    try:
        return json.loads(MESSAGES_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {
            "rate_limited": "Too many requests. Please try again later.",
            "upstream_unavailable": "Upstream service unavailable.",
            "health_ok": "ok",
        }


MESSAGES = _load_messages()


def _client_identity(request: Request) -> str:
    user = request.headers.get("x-user-id") or request.headers.get("x-identity-id")
    if user:
        return f"user:{user}"
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    return f"ip:{ip}"


def _path_skips_rate_limit(path: str) -> bool:
    for prefix in SKIP_RL_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
            return True
        if path.startswith(prefix):
            return True
    return False


def _header_skips_rate_limit(request: Request) -> bool:
    raw = request.headers.get(SKIP_RL_HEADER, "")
    return raw.strip().lower() in SKIP_RL_HEADER_VALUES


def _rate_limit_allow(identity: str) -> bool:
    key = f"{RATE_KEY_PREFIX}:{identity}"
    try:
        count = _redis.incr(key)
        if count == 1:
            _redis.expire(key, RATE_LIMIT_WINDOW_S)
        return int(count) <= RATE_LIMIT_REQUESTS
    except redis.RedisError:
        # Fail open on Valkey blip so chat is not bricked; log via response header
        return True


@app.on_event("startup")
async def _startup() -> None:
    global _http, MESSAGES
    MESSAGES = _load_messages()
    _http = httpx.AsyncClient(
        timeout=httpx.Timeout(PROXY_TIMEOUT_S),
        follow_redirects=True,
    )


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


@app.get("/health")
async def health() -> dict:
    return {"status": MESSAGES.get("health_ok", "ok"), "service": "api-gateway"}


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(full_path: str, request: Request) -> Response:
    path = "/" + full_path if full_path else "/"
    skip_rl = _path_skips_rate_limit(path) or _header_skips_rate_limit(request)
    if not skip_rl:
        identity = _client_identity(request)
        if not _rate_limit_allow(identity):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": MESSAGES.get(
                        "rate_limited", "Too many requests. Please try again later."
                    ),
                },
            )

    if _http is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "upstream_unavailable",
                "message": MESSAGES.get(
                    "upstream_unavailable", "Upstream service unavailable."
                ),
            },
        )

    url = f"{UPSTREAM_URL}{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length"}
    }
    body = await request.body()
    try:
        upstream = await _http.request(
            request.method,
            url,
            headers=headers,
            content=body,
        )
    except httpx.RequestError:
        return JSONResponse(
            status_code=503,
            content={
                "error": "upstream_unavailable",
                "message": MESSAGES.get(
                    "upstream_unavailable", "Upstream service unavailable."
                ),
            },
        )

    excluded = {"content-encoding", "transfer-encoding", "content-length", "connection"}
    out_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in excluded
    }
    if skip_rl:
        out_headers["x-gateway-rate-limit"] = "skipped-coding"
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get("content-type"),
    )
