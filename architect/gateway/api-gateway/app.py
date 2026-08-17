"""
API Gateway — VPN/LAN HTTP entry with shared Valkey rate limiting.

Zalo bridge/proxy must NOT hairpin through this service.
Auth is required when GATEWAY_API_KEYS is set (default when gateway is used).
Client headers must never grant RL bypass or spoof identity.
Admin-editable messages: messages/en.json
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock

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
# Path prefixes that skip RL *after* auth (server-side coding routes only).
# Header-based bypass is disabled (GATEWAY_SKIP_RL_HEADER ignored).
SKIP_RL_PATH_PREFIXES = tuple(
    p.strip()
    for p in os.environ.get(
        "GATEWAY_SKIP_RL_PATHS", "/coding,/v1/coding,/skills/coding"
    ).split(",")
    if p.strip()
)
MESSAGES_PATH = Path(
    os.environ.get(
        "GATEWAY_MESSAGES_FILE",
        str(Path(__file__).resolve().parent / "messages" / "en.json"),
    )
)
PROXY_TIMEOUT_S = float(os.environ.get("GATEWAY_PROXY_TIMEOUT_S", "120"))
GATEWAY_API_KEYS = {
    k.strip()
    for k in os.environ.get("GATEWAY_API_KEYS", "").split(",")
    if k.strip()
}
# Require keys whenever gateway runs unless explicitly set to 0 (lab escape hatch).
GATEWAY_REQUIRE_AUTH = os.environ.get("GATEWAY_REQUIRE_AUTH", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
GATEWAY_AUTH_ENABLED = os.environ.get(
    "GATEWAY_AUTH_ENABLED",
    "1" if (GATEWAY_API_KEYS or GATEWAY_REQUIRE_AUTH) else "0",
).strip().lower() in {"1", "true", "yes", "on"}
GATEWAY_MAX_BODY_BYTES = int(
    os.environ.get("GATEWAY_MAX_BODY_BYTES", str(32 * 1024 * 1024))
)
AUTH_HEADER = os.environ.get("GATEWAY_AUTH_HEADER", "authorization")
# Only trust X-Forwarded-For when behind a trusted proxy (Traefik). Default: off.
GATEWAY_TRUST_FORWARDED = os.environ.get(
    "GATEWAY_TRUST_FORWARDED", "0"
).strip().lower() in {"1", "true", "yes", "on"}
# Valkey blip: fail closed (deny) by default; local emergency limiter softens outage.
GATEWAY_RL_FAIL_CLOSED = os.environ.get(
    "GATEWAY_RL_FAIL_CLOSED", "1"
).strip().lower() in {"1", "true", "yes", "on"}
LOCAL_RL_MAX = int(os.environ.get("GATEWAY_LOCAL_RL_MAX", str(RATE_LIMIT_REQUESTS)))

app = FastAPI(title="hermes-stack-api-gateway", version="0.5.2")
_redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
_http: httpx.AsyncClient | None = None
_local_rl: dict[str, list[float]] = defaultdict(list)
_local_lock = Lock()


def _load_messages() -> dict:
    try:
        return json.loads(MESSAGES_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {
            "rate_limited": "Too many requests. Please try again later.",
            "upstream_unavailable": "Upstream service unavailable.",
            "unauthorized": "Unauthorized. Provide a valid API key.",
            "misconfigured": "Gateway misconfigured: set GATEWAY_API_KEYS.",
            "body_too_large": "Request body too large.",
            "health_ok": "ok",
        }


MESSAGES = _load_messages()


def _client_identity(request: Request, api_key: str) -> str:
    """Prefer authenticated key; never trust client-supplied user ids for RL."""
    if api_key:
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        return f"key:{digest}"
    if GATEWAY_TRUST_FORWARDED:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
            if ip:
                return f"ip:{ip}"
    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


def _path_skips_rate_limit(path: str) -> bool:
    for prefix in SKIP_RL_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
            return True
        if path.startswith(prefix):
            return True
    return False


def _extract_api_key(request: Request) -> str:
    auth = request.headers.get(AUTH_HEADER, "") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("x-api-key") or "").strip()


def _auth_ok(request: Request) -> bool:
    if GATEWAY_REQUIRE_AUTH or GATEWAY_AUTH_ENABLED:
        if not GATEWAY_API_KEYS:
            return False
        key = _extract_api_key(request)
        return bool(key) and key in GATEWAY_API_KEYS
    if not GATEWAY_API_KEYS:
        return True
    key = _extract_api_key(request)
    return bool(key) and key in GATEWAY_API_KEYS


def _local_rate_limit_allow(identity: str) -> bool:
    now = time.time()
    window = float(RATE_LIMIT_WINDOW_S)
    with _local_lock:
        bucket = _local_rl[identity]
        _local_rl[identity] = [t for t in bucket if now - t < window]
        if len(_local_rl[identity]) >= LOCAL_RL_MAX:
            return False
        _local_rl[identity].append(now)
        return True


def _rate_limit_allow(identity: str) -> bool:
    key = f"{RATE_KEY_PREFIX}:{identity}"
    try:
        count = _redis.incr(key)
        if count == 1:
            _redis.expire(key, RATE_LIMIT_WINDOW_S)
        return int(count) <= RATE_LIMIT_REQUESTS
    except redis.RedisError:
        if GATEWAY_RL_FAIL_CLOSED:
            return _local_rate_limit_allow(identity)
        return True


@app.on_event("startup")
async def _startup() -> None:
    global _http, MESSAGES
    MESSAGES = _load_messages()
    if (GATEWAY_REQUIRE_AUTH or GATEWAY_AUTH_ENABLED) and not GATEWAY_API_KEYS:
        raise RuntimeError(
            "GATEWAY_API_KEYS is required when API Gateway auth is enabled "
            "(set GATEWAY_REQUIRE_AUTH=0 only for isolated lab)"
        )
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
    return {
        "status": MESSAGES.get("health_ok", "ok"),
        "service": "api-gateway",
        "auth_required": bool(GATEWAY_REQUIRE_AUTH or GATEWAY_AUTH_ENABLED),
        "keys_configured": bool(GATEWAY_API_KEYS),
    }


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(full_path: str, request: Request) -> Response:
    path = "/" + full_path if full_path else "/"
    if path != "/health" and not _auth_ok(request):
        msg = (
            MESSAGES.get("misconfigured", "Gateway misconfigured: set GATEWAY_API_KEYS.")
            if (GATEWAY_REQUIRE_AUTH or GATEWAY_AUTH_ENABLED) and not GATEWAY_API_KEYS
            else MESSAGES.get("unauthorized", "Unauthorized. Provide a valid API key.")
        )
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": msg},
        )
    api_key = _extract_api_key(request)
    skip_rl = _path_skips_rate_limit(path)
    if not skip_rl:
        identity = _client_identity(request, api_key)
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
    if len(body) > GATEWAY_MAX_BODY_BYTES:
        return JSONResponse(
            status_code=413,
            content={
                "error": "body_too_large",
                "message": MESSAGES.get("body_too_large", "Request body too large."),
                "limit": GATEWAY_MAX_BODY_BYTES,
            },
        )
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
        out_headers["x-gateway-rate-limit"] = "skipped-coding-path"
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get("content-type"),
    )
