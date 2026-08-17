"""Model Router — task-aware LLM proxy (v0.5.0).

Routing (hybrid classification):
  1. Explicit client tag: X-Task-Type / body.metadata.task_type
  2. Hermes task_hint (metadata.task_hint)
  3. Heuristic from config/heuristic patterns
  4. Unknown → general

Providers:
  coding  → 9router (if healthy) else OmniRouter if only that exists → fallback pool
  general → OmniRouter (if enabled+healthy) else 9router → fallback pool

Missing API keys skip that provider. Ollama optional. Nothing left → clear error.
Admin-editable messages: messages/en.json
Heuristic patterns: config/heuristic.json (not hardcoded business rules in code).
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

ROOT = Path(__file__).resolve().parent
MESSAGES_PATH = Path(os.environ.get("MODEL_ROUTER_MESSAGES", str(ROOT / "messages" / "en.json")))
HEURISTIC_PATH = Path(os.environ.get("MODEL_ROUTER_HEURISTIC", str(ROOT / "config" / "heuristic.json")))

N9_BASE = os.environ.get("N9ROUTER_BASE_URL", "http://9router:20128/v1").rstrip("/")
OMNI_BASE = os.environ.get("OMNIROUTER_BASE_URL", "http://omni-router:20129/v1").rstrip("/")
ENABLE_OMNI = os.environ.get("ENABLE_OMNIROUTER", "0").strip() in {"1", "true", "yes", "on"}
N9_KEY = (os.environ.get("N9ROUTER_API_KEY") or "").strip()
OMNI_KEY = (os.environ.get("OMNIROUTER_API_KEY") or os.environ.get("N9ROUTER_API_KEY") or "").strip()
OLLAMA_BASE = (os.environ.get("OLLAMA_BASE_URL") or "").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
FALLBACK_OPENAI = (os.environ.get("FALLBACK_OPENAI_BASE_URL") or "").rstrip("/")
FALLBACK_OPENAI_KEY = (os.environ.get("OPENAI_API_KEY") or "").strip()
FALLBACK_OPENAI_MODEL = os.environ.get("FALLBACK_OPENAI_MODEL", "gpt-4o-mini")
TIMEOUT_S = float(os.environ.get("MODEL_ROUTER_TIMEOUT_S", "90"))
HEALTH_TTL_S = float(os.environ.get("MODEL_ROUTER_HEALTH_TTL_S", "15"))
LISTEN_PORT = int(os.environ.get("MODEL_ROUTER_PORT", "8096"))

app = FastAPI(title="assistant-model-router", version="0.5.0")
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
HEURISTIC = _load_json(
    HEURISTIC_PATH,
    {"coding_substrings": ["```", "def ", "function ", "import ", "error:", "stack trace", "compile"]},
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


def _classify(request: Request, body: dict) -> str:
    # 1) explicit header
    hdr = (request.headers.get("x-task-type") or request.headers.get("X-Task-Type") or "").strip().lower()
    if hdr in {"coding", "code", "general", "other"}:
        return "coding" if hdr in {"coding", "code"} else "general"
    meta = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
    # 2) Hermes hint
    for key in ("task_type", "task_hint", "task"):
        val = str(meta.get(key) or body.get(key) or "").strip().lower()
        if val in {"coding", "code"}:
            return "coding"
        if val in {"general", "other", "chat"}:
            return "general"
    # 3) heuristic
    blobs: list[str] = []
    for m in body.get("messages") or []:
        if isinstance(m, dict):
            c = m.get("content")
            if isinstance(c, str):
                blobs.append(c.lower())
            elif isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        blobs.append(part["text"].lower())
    text = "\n".join(blobs)
    for sub in HEURISTIC.get("coding_substrings") or []:
        if str(sub).lower() in text:
            return "coding"
    # 4) unknown → general
    return "general"


def _auth_headers(key: str) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


async def _candidates(task: str) -> list[tuple[str, str, dict[str, str], Optional[str]]]:
    """Return ordered (name, base_url, headers, default_model_override)."""
    out: list[tuple[str, str, dict[str, str], Optional[str]]] = []
    n9_ok = await _probe("9router", N9_BASE, _auth_headers(N9_KEY)) if N9_BASE else False
    omni_ok = False
    if ENABLE_OMNI and OMNI_BASE:
        omni_ok = await _probe("omni", OMNI_BASE, _auth_headers(OMNI_KEY))

    if task == "coding":
        if n9_ok:
            out.append(("9router", N9_BASE, _auth_headers(N9_KEY), None))
        elif omni_ok:
            out.append(("omni-router", OMNI_BASE, _auth_headers(OMNI_KEY), None))
    else:
        if omni_ok:
            out.append(("omni-router", OMNI_BASE, _auth_headers(OMNI_KEY), None))
        elif n9_ok:
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
    }


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
    task = _classify(request, body) if is_chat or body else "general"
    candidates = await _candidates(task)
    if not candidates:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": MESSAGES.get("no_model_available"), "type": "no_model_available", "task": task}},
        )

    stream = bool(body.get("stream")) if isinstance(body, dict) else False
    last_err = ""
    for name, base, headers, model_override in candidates:
        payload = dict(body) if body else {}
        if model_override and "model" in payload:
            payload["model"] = model_override
        elif model_override and is_chat:
            payload["model"] = model_override
        url = f"{base}/{path.lstrip('/')}"
        try:
            if stream and request.method == "POST":
                req = _client().build_request(
                    request.method,
                    url,
                    headers={**headers, **{k: v for k, v in request.headers.items() if k.lower() == "accept"}},
                    content=json.dumps(payload).encode("utf-8"),
                )
                upstream = await _client().send(req, stream=True)
                if upstream.status_code >= 500:
                    await upstream.aclose()
                    last_err = f"{name}:{upstream.status_code}"
                    continue

                async def gen():
                    async for chunk in upstream.aiter_bytes():
                        yield chunk
                    await upstream.aclose()

                return StreamingResponse(gen(), status_code=upstream.status_code, media_type=upstream.headers.get("content-type", "text/event-stream"))

            upstream = await _client().request(
                request.method,
                url,
                headers=headers,
                content=json.dumps(payload).encode("utf-8") if payload else raw,
            )
            if upstream.status_code >= 500:
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=LISTEN_PORT)
