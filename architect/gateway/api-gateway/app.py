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
try:
    import valkey  # type: ignore
except ImportError:  # pragma: no cover - local fallback until valkey is installed
    import redis as valkey  # type: ignore
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# ── constants (env-overridable) ─────────────────────────────────────────────
VALKEY_URL = os.environ.get("VALKEY_URL") or os.environ.get("REDIS_URL", "valkey://redis:6379/0")
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
WORKFLOW_URL = (os.environ.get("WORKFLOW_URL") or "http://workflow:8108").rstrip("/")
HERMES_WORKFLOW_ENABLED = os.environ.get("HERMES_WORKFLOW", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
HERMES_WORKFLOW_TIMEOUT_S = float(os.environ.get("HERMES_WORKFLOW_TIMEOUT_S", "90"))
HERMES_WORKFLOW_WAIT_S = float(os.environ.get("HERMES_WORKFLOW_WAIT_S", "20"))
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
_VALKEY_ERROR = getattr(valkey, "ValkeyError", None) or getattr(valkey, "RedisError", Exception)

app = FastAPI(title="hermes-stack-api-gateway", version="0.5.2")
_valkey_cls = getattr(valkey, "Valkey", None) or getattr(valkey, "Redis")
_redis = _valkey_cls.from_url(VALKEY_URL, decode_responses=True)
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


def _workflow_http(method: str, path: str, payload: dict | None = None) -> dict:
    try:
        with httpx.Client(timeout=HERMES_WORKFLOW_TIMEOUT_S) as client:
            r = client.request(method, f"{WORKFLOW_URL}{path}", json=payload)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {}
    except (httpx.HTTPError, ValueError):
        return {}


def _extract_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _latest_user_text(payload: dict) -> str:
    messages = payload.get("messages")
    if isinstance(messages, list):
        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue
            if str(msg.get("role") or "").lower() != "user":
                continue
            text = _extract_text(msg.get("content"))
            if text:
                return text
    return ""


def _numbered_bodies(raw: str) -> list[str]:
    import re

    items: list[tuple[int, str]] = []
    for m in re.finditer(r"(?m)^\s*(\d+)(?:[.)]\s*|\s+)(.+)$", raw or ""):
        n = int(m.group(1))
        if 1 <= n <= 20:
            body = m.group(2).strip()
            if body:
                items.append((n, body))
    if len(items) >= 2 and {1, 2}.issubset({n for n, _ in items}):
        items.sort(key=lambda x: x[0])
        return [body for _, body in items]
    marks: list[tuple[int, int, int]] = []
    for m in re.finditer(r"(?:^|(?<=\n)|(?<=[\s:]))(\d+)[.)]\s*", raw or ""):
        n = int(m.group(1))
        if 1 <= n <= 20:
            marks.append((n, m.end(), m.start()))
    if len(marks) < 2:
        return []
    out: list[tuple[int, str]] = []
    for i, (n, body_start, _tok) in enumerate(marks):
        end = marks[i + 1][2] if i + 1 < len(marks) else len(raw)
        body = (raw[body_start:end] or "").strip()
        if body:
            out.append((n, body))
    nums = {n for n, _ in out}
    if 1 not in nums or 2 not in nums:
        return []
    out.sort(key=lambda x: x[0])
    seen: set[int] = set()
    parts: list[str] = []
    for n, body in out:
        if n in seen:
            continue
        seen.add(n)
        parts.append(body)
    return parts


def _plan_instructions(text: str) -> list[str]:
    import re

    raw = (text or "").strip()
    if not raw:
        return []
    labeled = list(
        re.finditer(r"(?i)(?:tin\s+nhắn|message|msg|yêu\s+cầu|request)\s*(\d+)\s*[:.\-—]\s*", raw)
    )
    if len(labeled) >= 2:
        parts: list[str] = []
        for i, m in enumerate(labeled):
            start = m.end()
            end = labeled[i + 1].start() if i + 1 < len(labeled) else len(raw)
            chunk = raw[start:end].strip()
            if chunk:
                parts.append(chunk)
        if len(parts) >= 2:
            return parts
    numbered = _numbered_bodies(raw)
    if len(numbered) >= 2:
        return numbered
    return [raw]


def _looks_like_schedule(text: str) -> bool:
    import re

    low = (text or "").lower()
    if not low.strip():
        return False
    markers = (
        "hàng ngày",
        "hằng ngày",
        "mỗi ngày",
        "daily",
        "every day",
        "schedule",
        "đặt lịch",
        "hẹn giờ",
        "gmt+7",
        "gmt +7",
    )
    if any(m in low for m in markers):
        return True
    return len(_numbered_bodies(text)) >= 2 and bool(
        re.search(r"(?i)(?:\d{1,2}\s*[:h]\s*\d{2}\s*(?:am|pm|gmt|sáng|chiều|tối)|gmt\s*\+?\s*7)", low)
    )


def _chat_completion_ack(model: str, text: str, workflow: dict, *, scheduled: bool) -> dict:
    content = (
        "Saved schedule in Hermes workflow. Each numbered item will run as a durable job at the configured time."
        if scheduled
        else f"Accepted workflow with {len((workflow or {}).get('jobs') or [])} jobs. Hermes will run them durably in order."
    )
    return {
        "id": f"workflow-{workflow.get('id') or 'accepted'}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or "hermes-workflow",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "workflow": workflow,
        "accepted_text": text,
    }


def _aggregate_workflow_text(workflow: dict) -> str:
    jobs = workflow.get("jobs") if isinstance(workflow, dict) else None
    if not isinstance(jobs, list):
        return ""
    parts: list[str] = []
    for i, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            continue
        result = job.get("result") if isinstance(job.get("result"), dict) else {}
        text = ""
        if isinstance(result.get("text"), str) and result.get("text").strip():
            text = result["text"].strip()
        elif isinstance(result.get("raw"), dict):
            raw = result["raw"]
            choices = raw.get("choices")
            if isinstance(choices, list) and choices:
                msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                if isinstance(msg, dict):
                    text = _extract_text(msg.get("content"))
        if text:
            parts.append(f"{i}. {text}")
    return "\n\n".join(parts).strip()


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
    except _VALKEY_ERROR:
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
    if (
        HERMES_WORKFLOW_ENABLED
        and request.method.upper() == "POST"
        and path in {"/v1/chat/completions", "/chat/completions"}
        and body
    ):
        try:
            payload = json.loads(body.decode("utf-8"))
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            text = _latest_user_text(payload)
            model = str(payload.get("model") or "hermes-workflow")
            if text:
                context = {
                    "execute": "hermes_http",
                    "model": model,
                    "api_url": os.environ.get("HERMES_API_URL") or "http://hermes:8642/v1/chat/completions",
                    "api_key": os.environ.get("API_SERVER_KEY") or "",
                }
                if _looks_like_schedule(text):
                    data = _workflow_http(
                        "POST",
                        "/v1/schedules",
                        {
                            "name": text[:60],
                            "text": text,
                            "timezone": os.environ.get("TZ") or "Asia/Ho_Chi_Minh",
                            "origin": {"platform": "hermes-api", "path": path},
                            "context": context,
                        },
                    )
                    schedule = data.get("schedule") if isinstance(data, dict) else None
                    if isinstance(schedule, dict) and schedule.get("id"):
                        return JSONResponse(
                            status_code=200,
                            content=_chat_completion_ack(model, text, schedule, scheduled=True),
                        )
                instructions = _plan_instructions(text)
                if len(instructions) >= 2:
                    data = _workflow_http(
                        "POST",
                        "/v1/workflows",
                        {
                            "instructions": instructions,
                            "origin": {"platform": "hermes-api", "path": path},
                            "context": context,
                            "sequential": True,
                            "wrap": True,
                        },
                    )
                    workflow = data.get("workflow") if isinstance(data, dict) else None
                    if isinstance(workflow, dict) and workflow.get("id"):
                        waited = _workflow_http(
                            "POST",
                            f"/v1/workflows/{workflow['id']}/wait",
                            {"timeout_s": min(HERMES_WORKFLOW_TIMEOUT_S, HERMES_WORKFLOW_WAIT_S)},
                        )
                        done = waited.get("workflow") if isinstance(waited, dict) else None
                        if isinstance(done, dict) and str(done.get("status") or "") == "COMPLETED":
                            content = _aggregate_workflow_text(done)
                            if content:
                                return JSONResponse(
                                    status_code=200,
                                    content={
                                        "id": f"workflow-{done.get('id')}",
                                        "object": "chat.completion",
                                        "created": int(time.time()),
                                        "model": model,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "message": {"role": "assistant", "content": content},
                                                "finish_reason": "stop",
                                            }
                                        ],
                                        "workflow": done,
                                    },
                                )
                        return JSONResponse(
                            status_code=200,
                            content=_chat_completion_ack(model, text, workflow, scheduled=False),
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
