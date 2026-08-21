"""Model Router — task-aware LLM proxy (v0.5.0).

Routing:
  1. Explicit client tag: X-Task-Type / body.metadata.task_hint
  2. Default → normal (fast path). No substring / split NLU.
  3. POST /v1/classify uses an LLM and returns structured JSON.

Providers:
  coding  → 9router (if healthy) else OmniRouter if only that exists → fallback pool
  general / classify / outbound → OmniRouter (default) else 9router → fallback pool

Missing API keys skip that provider. Ollama optional. Nothing left → clear error.
Admin-editable messages: messages/en.json
Classify prompt: config/classify.json
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from classify import (  # noqa: E402
    TASK_HINTS,
    classify_with_llm,
    failed_plan,
    heuristic_plan,
    normalize_plan,
    outbound_with_llm,
    plan_schema_ok,
)
from chat_norm import (  # noqa: E402
    chat_body_should_failover,
    completion_to_sse,
    normalize_chat_completion,
    sanitize_chat_payload,
)
from route_expand import expand_chat_candidates
from websearch import health_fields as websearch_health
from websearch import router as websearch_router

ROOT = Path(__file__).resolve().parent
MESSAGES_PATH = Path(os.environ.get("MODEL_ROUTER_MESSAGES", str(ROOT / "messages" / "en.json")))

N9_BASE = os.environ.get("N9ROUTER_BASE_URL", "http://9router:20128/v1").rstrip("/")
OMNI_BASE = os.environ.get("OMNIROUTER_BASE_URL", "http://omni-router:20129/v1").rstrip("/")
ENABLE_OMNI = os.environ.get("ENABLE_OMNIROUTER", "1").strip() in {"1", "true", "yes", "on"}
ENABLE_9ROUTER = os.environ.get("ENABLE_9ROUTER", "0").strip() in {"1", "true", "yes", "on"}
N9_KEY = (os.environ.get("N9ROUTER_API_KEY") or "").strip()
OMNI_KEY = (os.environ.get("OMNIROUTER_API_KEY") or os.environ.get("N9ROUTER_API_KEY") or "").strip()
OMNI_DEFAULT_MODEL = (
    os.environ.get("OMNIROUTER_DEFAULT_COMBO") or os.environ.get("MODEL_ROUTER_OUTBOUND_MODEL") or "hermes"
).strip() or "hermes"
# After blocked/slow Omni members, try these free-safe ids (combo or model).
OMNI_FAILOVER_MODELS = [
    x.strip()
    for x in (
        os.environ.get("OMNIROUTER_FAILOVER_MODELS") or "auto/best-free"
    ).split(",")
    if x.strip()
]
# Retry the primary combo so Omni round-robin can land on an alive free member.
OMNI_ROTATE_ATTEMPTS = max(
    1, min(int(os.environ.get("OMNIROUTER_ROTATE_ATTEMPTS") or "3"), 8)
)
OLLAMA_BASE = (os.environ.get("OLLAMA_BASE_URL") or "").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
FALLBACK_OPENAI = (os.environ.get("FALLBACK_OPENAI_BASE_URL") or "").rstrip("/")
FALLBACK_OPENAI_KEY = (os.environ.get("OPENAI_API_KEY") or "").strip()
FALLBACK_OPENAI_MODEL = os.environ.get("FALLBACK_OPENAI_MODEL", "gpt-4o-mini")
# Free Omni models can be slow; give them room before rotating.
TIMEOUT_S = float(os.environ.get("MODEL_ROUTER_TIMEOUT_S", "180"))
HEALTH_TTL_S = float(os.environ.get("MODEL_ROUTER_HEALTH_TTL_S", "15"))
LISTEN_PORT = int(os.environ.get("MODEL_ROUTER_PORT", "8096"))
# Retry next provider on these (413 payload, 429 rate, auth, 5xx).
FAILOVER_HTTP = {401, 403, 413, 429}


def _failover_status(code: int) -> bool:
    return code >= 500 or code in FAILOVER_HTTP


def _expand_chat_candidates(
    candidates: list[tuple[str, str, dict[str, str], Optional[str]]],
    *,
    requested_model: str,
) -> list[tuple[str, str, dict[str, str], Optional[str]]]:
    return expand_chat_candidates(
        candidates,
        requested_model=requested_model,
        default_model=OMNI_DEFAULT_MODEL,
        failover_models=OMNI_FAILOVER_MODELS,
        rotate_attempts=OMNI_ROTATE_ATTEMPTS,
    )

app = FastAPI(title="assistant-model-router", version="0.5.0")
# Web search combo must be registered before the OpenAI proxy catch-all below.
app.include_router(websearch_router)
_http: httpx.AsyncClient | None = None
_health_cache: dict[str, tuple[float, bool]] = {}


def _load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return default


MESSAGES = _load_json(
    MESSAGES_PATH,
    {
        "no_model_available": "No model available. Configure 9router, OmniRouter, Ollama, or a fallback provider.",
        "upstream_error": "Upstream model provider error.",
        "health_ok": "ok",
    },
)


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=TIMEOUT_S)
    return _http


async def _probe(name: str, url: str, headers: Optional[dict] = None) -> bool:
    now = time.time()
    hit = _health_cache.get(name)
    if hit and now - hit[0] < HEALTH_TTL_S:
        return hit[1]
    ok = False
    try:
        r = await _client().get(f"{url}/models", headers=headers or {}, timeout=5.0)
        ok = r.status_code < 500
    except Exception:
        ok = False
    _health_cache[name] = (now, ok)
    return ok


TASK_ALIASES = {
    "code": "coding",
    "general": "normal",
    "other": "normal",
    "chat": "normal",
}
# SECRET is never a task_hint — security_status lives on Secret Probe.
PROVIDER_CODING = {"coding"}


def _normalize_hint(raw: str) -> str | None:
    val = (raw or "").strip().lower()
    if not val or val in {"secret", "blocked", "sensitive"}:
        return None
    if val in TASK_ALIASES:
        return TASK_ALIASES[val]
    if val in TASK_HINTS:
        return val
    return None


def _classify(request: Request, body: dict) -> str:
    hdr = (request.headers.get("x-task-type") or request.headers.get("X-Task-Type") or "").strip()
    mapped = _normalize_hint(hdr)
    if mapped:
        return mapped
    meta = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
    for key in ("task_type", "task_hint", "task"):
        mapped = _normalize_hint(str(meta.get(key) or body.get(key) or ""))
        if mapped:
            return mapped
    return "normal"


def _auth_headers(key: str) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


async def _candidates(task: str, *, prefer_omni: bool | None = None) -> list[tuple[str, str, dict[str, str], Optional[str]]]:
    """Return ordered (name, base_url, headers, default_model_override)."""
    out: list[tuple[str, str, dict[str, str], Optional[str]]] = []
    n9_ok = (
        ENABLE_9ROUTER
        and N9_BASE
        and await _probe("9router", N9_BASE, _auth_headers(N9_KEY))
    )
    omni_ok = False
    if ENABLE_OMNI and OMNI_BASE:
        omni_ok = await _probe("omni", OMNI_BASE, _auth_headers(OMNI_KEY))

    coding = task in PROVIDER_CODING
    use_omni_first = (not coding) if prefer_omni is None else prefer_omni
    if coding or not use_omni_first:
        if n9_ok:
            out.append(("9router", N9_BASE, _auth_headers(N9_KEY), None))
        if omni_ok:
            out.append(("omni-router", OMNI_BASE, _auth_headers(OMNI_KEY), None))
    else:
        if omni_ok:
            out.append(("omni-router", OMNI_BASE, _auth_headers(OMNI_KEY), None))
        if n9_ok:
            out.append(("9router", N9_BASE, _auth_headers(N9_KEY), None))

    if FALLBACK_OPENAI and FALLBACK_OPENAI_KEY:
        out.append(
            (
                "openai-fallback",
                FALLBACK_OPENAI,
                _auth_headers(FALLBACK_OPENAI_KEY),
                FALLBACK_OPENAI_MODEL,
            )
        )
    if OLLAMA_BASE:
        out.append(("ollama", f"{OLLAMA_BASE}/v1", {}, OLLAMA_MODEL))
    return out


def _bearer_key(headers: dict[str, str]) -> str:
    auth = str(headers.get("Authorization") or "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


@app.get("/health")
async def health() -> dict[str, Any]:
    n9 = await _probe("9router", N9_BASE, _auth_headers(N9_KEY)) if N9_BASE else False
    omni = False
    if ENABLE_OMNI:
        omni = await _probe("omni", OMNI_BASE, _auth_headers(OMNI_KEY))
    return {
        "ok": True,
        "service": "model-router",
        "status": MESSAGES.get("health_ok", "ok"),
        "nine_router": n9,
        "omni_router": omni,
        "enable_omni": ENABLE_OMNI,
        "task_hints": list(TASK_HINTS),
        "classify": "/v1/classify",
        "outbound": "/v1/outbound",
        "search": "/v1/search",
        **websearch_health(),
    }


@app.post("/v1/classify")
async def classify_endpoint(request: Request) -> dict[str, Any]:
    raw = await request.body()
    body: dict = {}
    if raw:
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}
    text = str(body.get("text") or "")
    timezone = str(body.get("timezone") or os.environ.get("TZ") or "Asia/Ho_Chi_Minh")
    last: dict[str, Any] = {}
    candidates = await _candidates("normal")
    for _name, base, headers, model in candidates:
        last = await classify_with_llm(
            text,
            timezone=timezone,
            client=_client(),
            n9_base=base,
            n9_key=_bearer_key(headers),
            model=model,
        )
        if last.get("ok"):
            return last
    guess = heuristic_plan(text)
    if guess:
        plan = normalize_plan(guess, text, timezone)
        if plan_schema_ok(plan):
            return plan
    return last or failed_plan(timezone, "classify_llm_failed")


@app.post("/v1/outbound")
async def outbound_endpoint(request: Request) -> dict[str, Any]:
    raw = await request.body()
    body: dict = {}
    if raw:
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}
    text = str(body.get("text") or "")
    last: dict[str, Any] = {}
    candidates = await _candidates("normal")
    if candidates:
        _name, base, headers, model = candidates[0]
        last = await outbound_with_llm(
            text,
            client=_client(),
            n9_base=base,
            n9_key=_bearer_key(headers),
            model=model,
        )
        if last.get("ok") and str(last.get("action") or "") in {"send", "drop"}:
            return last
    return last or {"ok": False, "action": "drop", "error": "outbound_llm_failed"}


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy(path: str, request: Request) -> Response:
    raw = await request.body()
    body: dict = {}
    if raw:
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}

    is_chat = path.rstrip("/").endswith("chat/completions") or path == "chat/completions"
    task = _classify(request, body) if is_chat or body else "normal"
    candidates = await _candidates(task)
    if not candidates:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": MESSAGES.get("no_model_available"), "type": "no_model_available", "task": task}},
        )

    want_stream = bool(body.get("stream")) if isinstance(body, dict) else False
    if is_chat:
        candidates = _expand_chat_candidates(
            candidates,
            requested_model=str((body or {}).get("model") or OMNI_DEFAULT_MODEL),
        )

    last_err = ""
    for name, base, headers, model_override in candidates:
        payload = sanitize_chat_payload(dict(body) if body else {})
        # Always call chat upstream non-stream so we can inspect error bodies
        # (paid Omni models often 403 inside a 200 SSE stream Hermes cannot recover from).
        if is_chat:
            payload["stream"] = False
        if model_override and "model" in payload:
            payload["model"] = model_override
        elif model_override and is_chat:
            payload["model"] = model_override
        url = f"{base}/{path.lstrip('/')}"
        try:
            if (not is_chat) and stream_passthrough_ok(want_stream, request.method):
                req = _client().build_request(
                    request.method,
                    url,
                    headers={**headers, **{k: v for k, v in request.headers.items() if k.lower() == "accept"}},
                    content=json.dumps(payload).encode("utf-8"),
                )
                upstream = await _client().send(req, stream=True)
                if _failover_status(upstream.status_code):
                    await upstream.aclose()
                    last_err = f"{name}:{upstream.status_code}"
                    continue
                ctype = str(upstream.headers.get("content-type") or "").lower()
                if "event-stream" not in ctype:
                    raw_body = await upstream.aread()
                    await upstream.aclose()
                    return Response(
                        content=raw_body,
                        status_code=upstream.status_code,
                        media_type=upstream.headers.get("content-type", "application/json"),
                        headers={"x-model-router-provider": name, "x-model-router-task": task},
                    )

                async def gen():
                    async for chunk in upstream.aiter_bytes():
                        yield chunk
                    await upstream.aclose()

                return StreamingResponse(
                    gen(),
                    status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type", "text/event-stream"),
                )

            upstream = await _client().request(
                request.method,
                url,
                headers=headers,
                content=json.dumps(payload).encode("utf-8") if payload else raw,
            )
            if is_chat:
                try:
                    parsed = json.loads(upstream.content.decode("utf-8", errors="replace") or "{}")
                except Exception:
                    parsed = None
                if chat_body_should_failover(upstream.status_code, parsed):
                    last_err = f"{name}:{upstream.status_code}:{str((parsed or {}).get('error') or 'bad_chat')[:80]}"
                    print(f"[route] failover {last_err} model={payload.get('model')}", flush=True)
                    continue
                norm = normalize_chat_completion(parsed)
                if norm is None:
                    last_err = f"{name}:bad_chat_json"
                    continue
                headers_out = {
                    "x-model-router-provider": name,
                    "x-model-router-task": task,
                    "x-model-router-model": str(payload.get("model") or ""),
                }
                if want_stream:
                    return StreamingResponse(
                        iter([completion_to_sse(norm)]),
                        status_code=200,
                        media_type="text/event-stream",
                        headers=headers_out,
                    )
                return JSONResponse(content=norm, status_code=200, headers=headers_out)

            if _failover_status(upstream.status_code):
                last_err = f"{name}:{upstream.status_code}"
                continue
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
                headers={"x-model-router-provider": name, "x-model-router-task": task},
            )
        except Exception as e:
            last_err = f"{name}:{e}"
            continue

    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "message": MESSAGES.get("no_model_available"),
                "type": "no_model_available",
                "task": task,
                "detail": last_err or MESSAGES.get("upstream_error"),
            }
        },
    )


def stream_passthrough_ok(want_stream: bool, method: str) -> bool:
    return bool(want_stream) and method == "POST"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=LISTEN_PORT)
