"""assistant dispatcher — round-robin web backends + media download/convert.

Backends: tavily, firecrawl (and optional exa). Hermes calls this instead of
picking a single vendor. See Exa vs Tavily / Firecrawl competitor notes in docs.
"""
from __future__ import annotations

import itertools
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from video_summary import health_fields, register_video_summary

app = FastAPI(title="assistant dispatcher", version="1.0.0")

SESSION_URL = os.environ.get("SESSION_URL", "http://session:8107").rstrip("/")
N9_UPSTREAM = os.environ.get("OPENAI_BASE_URL", "http://9router:20128/v1").rstrip("/")


def _timing_enabled() -> bool:
    """Always record phase clocks; adapter decides whether to print the footer."""
    v = (os.environ.get("ZALO_TIMING_RECORD") or "1").strip().lower()
    return v not in {"0", "false", "no", "off"}


def _timing_add(field: str, seconds: float, thread_id: Optional[str] = None) -> None:
    """Accumulate workflow/LLM seconds onto the active Zalo turn (session Redis)."""
    if not _timing_enabled() or seconds < 0.001:
        return
    try:
        with httpx.Client(timeout=1.5) as c:
            c.post(
                f"{SESSION_URL}/v1/timing/add",
                json={"field": field, "seconds": seconds, "thread_id": thread_id or ""},
            )
    except Exception:
        pass


@app.middleware("http")
async def _time_workflow(request: Request, call_next):
    path = request.url.path or ""
    if path.startswith("/v1/") and not path.startswith("/openai"):
        t0 = time.time()
        resp = await call_next(request)
        _timing_add("workflow_s", time.time() - t0)
        return resp
    return await call_next(request)


@app.api_route("/openai/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def openai_proxy(path: str, request: Request):
    """Time Hermes LLM calls (chat/completions start→end) then forward to 9router."""
    import json as _json

    t0 = time.time()
    url = f"{N9_UPSTREAM}/{path.lstrip('/')}"
    body = await request.body()
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length", "connection"}
    }
    stream = False
    is_llm = path.rstrip("/").endswith("chat/completions") or path.rstrip("/").endswith(
        "completions"
    )
    if body:
        try:
            stream = bool(_json.loads(body).get("stream"))
        except Exception:
            stream = False
    timeout = httpx.Timeout(180.0, connect=10.0)
    if stream:
        client = httpx.AsyncClient(timeout=timeout)

        async def gen():
            try:
                async with client.stream(
                    request.method, url, content=body, headers=headers
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
            finally:
                if is_llm:
                    _timing_add("llm_s", time.time() - t0)
                await client.aclose()

        return StreamingResponse(gen(), media_type="text/event-stream")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(request.method, url, content=body, headers=headers)
    if is_llm:
        _timing_add("llm_s", time.time() - t0)
    out_headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}
    }
    return Response(content=resp.content, status_code=resp.status_code, headers=out_headers)

MEDIA_DIR = Path(os.environ.get("MEDIA_CACHE_DIR", "/data/media"))
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Empty WEB_BACKENDS = web search off (Low). Medium profile.sh sets tavily,firecrawl.
_web_raw = os.environ.get("WEB_BACKENDS")
if _web_raw is None:
    BACKENDS = ["tavily", "firecrawl"]
else:
    BACKENDS = [b.strip().lower() for b in _web_raw.split(",") if b.strip()]
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng:8080").rstrip("/")
SEARXNG_MAX = int(os.environ.get("SEARXNG_MAX_RESULTS", "5"))

_lock = threading.Lock()
_cycle = itertools.cycle(BACKENDS) if BACKENDS else None


def next_backend() -> str:
    if not _cycle:
        raise HTTPException(503, "web search disabled (WEB_BACKENDS empty)")
    with _lock:
        return next(_cycle)


def _key(name: str) -> str:
    return os.environ.get(f"{name.upper()}_API_KEY", "").strip()


class SearchReq(BaseModel):
    query: str
    max_results: int = 5
    backend: Optional[str] = None  # force; else RR


class ExtractReq(BaseModel):
    url: str
    backend: Optional[str] = None


class MediaReq(BaseModel):
    url: str
    convert: str = Field(default="auto", description="auto|mp3|mp4|image|keep")
    filename: Optional[str] = None


class ModeReq(BaseModel):
    """Soft switch: chat | research | upload | code (+ optional caption)."""
    mode: str
    text: str = ""
    has_media: bool = False


class ImageReq(BaseModel):
    """Generate an image; optionally refine via LLM then push to Zalo."""
    prompt: str
    filename: Optional[str] = None
    provider: Optional[str] = None  # llm|vendor|comfy-cpu|comfy-gpu|pollinations (paid1/paid2 aliases ok)
    thread_id: Optional[str] = None
    thread_type: str = "group"
    send_zalo: bool = False
    caption: str = ""
    refine: bool = True  # DeepSeek/LLM rewrite prompt before gen; wait for reply


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "backends": BACKENDS,
        "keys": {
            "tavily": bool(_key("tavily")),
            "firecrawl": bool(_key("firecrawl")),
            "exa": bool(_key("exa")),
            "deepseek": bool(
                os.environ.get("DEEPSEEK_API_KEY")
                or os.environ.get("DEEPSEEK_OCR_API_KEY")
                or ""
            ),
            "n9router": bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("N9ROUTER_API_KEY") or ""),
        },
        "media_dir": str(MEDIA_DIR),
        "image_backends": [
            b.strip()
            for b in (os.environ.get("IMAGE_BACKENDS") or "").split(",")
            if b.strip()
        ],
        "image_provider": os.environ.get("IMAGE_PROVIDER", ""),
        "comfyui_has_gpu": (os.environ.get("COMFYUI_HAS_GPU") or "0") != "0",
        "zalo_bridge": bool(os.environ.get("ZALO_BRIDGE_URL", "").strip()),
        "whisper_model": os.environ.get("WHISPER_MODEL", "tiny"),
        "whisper_enabled": os.environ.get("WHISPER_ENABLED", "1") != "0",
        "searxng": bool(SEARXNG_URL),
        **health_fields(MEDIA_DIR),
    }


@app.get("/v1/backends/next")
def backends_next() -> dict[str, str]:
    return {"backend": next_backend()}


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
        # Firecrawl search/scrape — adjust path if your plan uses /v1/search
        r = await client.post(
            "https://api.firecrawl.dev/v1/search",
            headers={"Authorization": f"Bearer {key}"},
            json={"query": query, "limit": max_results},
        )
        if r.status_code == 404:
            # fallback: map → scrape first result via extract pattern not available
            raise HTTPException(502, f"firecrawl search unavailable: {r.text[:200]}")
        r.raise_for_status()
        data = r.json()
        return {"backend": "firecrawl", "results": data.get("data") or data.get("results") or data}


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
    """Local SearXNG JSON — last-resort web search (top N, default 5)."""
    if not SEARXNG_URL:
        raise HTTPException(503, "SEARXNG_URL missing")
    n = max(1, min(int(max_results or SEARXNG_MAX), SEARXNG_MAX, 10))
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        r = await client.get(
            f"{SEARXNG_URL}/search",
            params={"q": query, "format": "json", "language": "all"},
        )
        r.raise_for_status()
        data = r.json()
    raw = data.get("results") or []
    results = []
    for item in raw[:n]:
        results.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or item.get("link") or "",
                "content": (item.get("content") or item.get("snippet") or "")[:500],
                "engine": item.get("engine") or "",
            }
        )
    if not results:
        raise RuntimeError("searxng returned no results")
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


@app.post("/v1/search")
async def search(req: SearchReq) -> dict[str, Any]:
    n = max(1, min(int(req.max_results or 5), 10))
    order = [req.backend.lower()] if req.backend else []
    if not order:
        if not BACKENDS:
            raise HTTPException(503, "web search disabled (WEB_BACKENDS empty)")
        first = next_backend()
        order = [first] + [b for b in BACKENDS if b != first]
    # Medium+: after paid vendors, fall back to local SearXNG (top 5).
    if BACKENDS and "searxng" not in order:
        order.append("searxng")
    errors: list[str] = []
    for b in order:
        try:
            if b == "tavily":
                return await _tavily_search(req.query, n)
            if b == "firecrawl":
                return await _firecrawl_search(req.query, n)
            if b == "exa":
                return await _exa_search(req.query, n)
            if b == "searxng":
                return await _searxng_search(req.query, n)
            errors.append(f"unknown backend {b}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{b}: {e}")
            continue
    raise HTTPException(502, {"error": "all backends failed", "detail": errors})


@app.post("/v1/extract")
async def extract(req: ExtractReq) -> dict[str, Any]:
    order = [req.backend.lower()] if req.backend else []
    if not order:
        if not BACKENDS:
            raise HTTPException(503, "web extract disabled (WEB_BACKENDS empty)")
        first = next_backend()
        order = [first] + [b for b in BACKENDS if b != first]
    errors: list[str] = []
    for b in order:
        try:
            if b == "tavily":
                return await _tavily_extract(req.url)
            if b == "firecrawl":
                return await _firecrawl_extract(req.url)
            errors.append(f"unsupported extract backend {b}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{b}: {e}")
            continue
    raise HTTPException(502, {"error": "all extract backends failed", "detail": errors})


@app.post("/v1/mode")
def mode_switch(req: ModeReq) -> dict[str, Any]:
    """Return which skill/mode Hermes should prefer (soft switch, not slash-required)."""
    m = req.mode.strip().lower()
    text = (req.text or "").lower()
    if m not in {"chat", "research", "upload", "code", "auto"}:
        raise HTTPException(400, "mode must be chat|research|upload|code|auto")
    if m == "auto":
        if req.has_media or any(k in text for k in ("phân tích", "đọc ảnh", "ocr", "đây là gì")):
            m = "upload"
        elif any(
            k in text
            for k in (
                "giá",
                "tin tức",
                "search",
                "tra cứu",
                "tóm tắt",
                "tom tat",
                "http",
            )
        ):
            m = "research"
        elif any(k in text for k in ("code", "bug", "stacktrace", "function", "refactor")):
            m = "code"
        else:
            m = "chat"
    hints = {
        "chat": "Use skill chat + common-rules.",
        "research": "Use skill research; web→/v1/search.",
        "upload": "Use skill upload/vision/ocr; media already local or via /v1/media.",
        "code": "Use skill code; short snippets.",
    }
    return {"mode": m, "hint": hints[m], "datetime_rule": "Timezone TZ=Asia/Ho_Chi_Minh. Do not invent a ⏱ footer; adapter appends measured phases."}



class TranscribeReq(BaseModel):
    """Transcribe a local media file under MEDIA_DIR."""

    path: str
    language: Optional[str] = None



_whisper_model = None
_whisper_lock = threading.Lock()


def _whisper_transcribe(path: Path, language: Optional[str] = None) -> str:
    if os.environ.get("WHISPER_ENABLED", "1") == "0":
        raise RuntimeError("WHISPER_ENABLED=0")
    global _whisper_model
    model_name = os.environ.get("WHISPER_MODEL", "tiny")
    with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel

            _whisper_model = WhisperModel(
                model_name,
                device=os.environ.get("WHISPER_DEVICE", "cpu"),
                compute_type=os.environ.get("WHISPER_COMPUTE", "int8"),
            )
        model = _whisper_model
    segments, _info = model.transcribe(
        str(path),
        language=language or None,
        vad_filter=True,
        beam_size=1,
    )
    parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if not text:
        raise RuntimeError("whisper returned empty transcript")
    return text


register_video_summary(app, MEDIA_DIR, _whisper_transcribe)


@app.post("/v1/media")
def media_download(req: MediaReq) -> dict[str, Any]:
    """Download URL to local cache (direct HTTP)."""
    parsed = urlparse(req.url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "url must be http(s)")
    job = uuid.uuid4().hex[:12]
    out_dir = MEDIA_DIR / job
    out_dir.mkdir(parents=True, exist_ok=True)
    name = req.filename or "download"
    convert = (req.convert or "auto").lower()

    try:
        dest = out_dir / name
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            r = client.get(req.url)
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            ext = ".bin"
            if "image/" in ctype:
                ext = "." + ctype.split("/")[-1].split(";")[0]
            elif "pdf" in ctype:
                ext = ".pdf"
            if not dest.suffix:
                dest = dest.with_suffix(ext)
            dest.write_bytes(r.content)
            if convert == "image" and dest.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                try:
                    from PIL import Image

                    img = Image.open(dest)
                    jpg = dest.with_suffix(".jpg")
                    img.convert("RGB").save(jpg, quality=90)
                    dest = jpg
                except Exception:  # noqa: BLE001
                    pass
        files = sorted(p for p in out_dir.iterdir() if p.is_file())
        return {
            "ok": True,
            "job": job,
            "files": [str(p) for p in files],
            "local_dir": str(out_dir),
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e


@app.post("/v1/transcribe")
def transcribe(req: TranscribeReq) -> dict[str, Any]:
    """ASR a local file under MEDIA_DIR."""
    src = Path(req.path)
    if not src.is_file():
        raise HTTPException(400, f"path not found: {req.path}")
    try:
        src.resolve().relative_to(MEDIA_DIR.resolve())
    except ValueError as e:
        raise HTTPException(400, "path must be under media cache") from e
    try:
        text = _whisper_transcribe(src, req.language)
        return {"ok": True, "source": "whisper", "transcript": text, "file": str(src)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e



def _pillow_stub(prompt: str, dest: Path) -> None:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (768, 512), (24, 48, 72))
    d = ImageDraw.Draw(im)
    low = (prompt or "").lower()
    # Simple keyword drawings so JPEG is never blank when APIs fail
    if any(k in low for k in ("mặt trời", "mat troi", "sun", "ông trời", "ong mat")):
        d.ellipse((280, 120, 480, 320), fill=(255, 200, 40), outline=(255, 140, 0), width=4)
        for ang in range(0, 360, 30):
            import math

            rad = math.radians(ang)
            x1, y1 = 380 + 110 * math.cos(rad), 220 + 110 * math.sin(rad)
            x2, y2 = 380 + 160 * math.cos(rad), 220 + 160 * math.sin(rad)
            d.line((x1, y1, x2, y2), fill=(255, 180, 30), width=6)
        d.ellipse((340, 180, 370, 210), fill=(40, 40, 40))
        d.ellipse((390, 180, 420, 210), fill=(40, 40, 40))
        d.arc((340, 230, 420, 280), 20, 160, fill=(40, 40, 40), width=4)
    elif any(k in low for k in ("khỉ", "khi", "monkey")):
        d.ellipse((280, 140, 480, 340), fill=(120, 80, 40))
        d.ellipse((300, 160, 360, 220), fill=(90, 60, 30))
        d.ellipse((400, 160, 460, 220), fill=(90, 60, 30))
        d.ellipse((340, 220, 370, 250), fill=(20, 20, 20))
        d.ellipse((390, 220, 420, 250), fill=(20, 20, 20))
    else:
        d.rectangle((40, 40, 728, 472), outline=(200, 180, 80), width=3)
    text = (prompt or "assistant")[:180]
    y = 400
    for i in range(0, min(len(text), 96), 48):
        d.text((56, y), text[i : i + 48], fill=(240, 240, 240))
        y += 22
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, quality=88)


def _refine_prompt_llm(prompt: str) -> tuple[str, dict[str, Any]]:
    """Wait for DeepSeek (or 9Router chat) to rewrite an image prompt. Sync."""
    meta: dict[str, Any] = {"refined": False}
    system = (
        "You rewrite user image requests into a concise English image-generation prompt. "
        "Output ONLY the prompt, no quotes or explanation. Keep subject, style, jpeg-friendly."
    )
    # Prefer DeepSeek chat API (not image — DeepSeek cloud has no hosted image-gen)
    ds_key = (
        os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("DEEPSEEK_OCR_API_KEY")
        or ""
    ).strip()
    ds_base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    ds_model = os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-chat")
    oa_base = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    oa_key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("N9ROUTER_API_KEY") or "").strip()
    oa_model = os.environ.get("REFINE_MODEL") or os.environ.get("HERMES_MODEL") or "hermes"

    attempts: list[tuple[str, str, str, str]] = []
    # Prefer 9Router/Hermes first when DeepSeek billing may be exhausted (402)
    if oa_base and oa_key:
        attempts.append(("openai", oa_base, oa_key, oa_model))
    if ds_key:
        attempts.append(("deepseek", ds_base, ds_key, ds_model))

    for name, base, key, model in attempts:
        try:
            with httpx.Client(timeout=90.0) as client:
                r = client.post(
                    f"{base}/chat/completions",
                    headers={
                        "authorization": f"Bearer {key}",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.4,
                        "max_tokens": 200,
                    },
                )
                r.raise_for_status()
                data = r.json()
                content = (
                    ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                    or ""
                ).strip()
                if content:
                    meta.update({"refined": True, "via": name, "model": model, "raw": content[:300]})
                    return content.strip("\"' \n"), meta
                meta.setdefault("errors", []).append(f"{name}: empty content")
        except Exception as e:  # noqa: BLE001
            meta.setdefault("errors", []).append(f"{name}: {e}")
    return prompt, meta


def _gen_pollinations(prompt: str) -> bytes:
    from urllib.parse import quote

    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=768&height=512&nologo=true"
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        if "image" not in r.headers.get("content-type", "") and len(r.content) < 1000:
            raise RuntimeError(f"pollinations bad response ctype={r.headers.get('content-type')}")
        return r.content


def _gen_openai(prompt: str) -> bytes:
    """OpenAI-compatible images API via 9Router (or any gateway). Not DeepSeek chat API."""
    base = os.environ.get("OPENAI_BASE_URL", "http://9router:20128/v1").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("N9ROUTER_API_KEY") or ""
    model = os.environ.get("IMAGE_MODEL", "dall-e-3")
    headers = {"content-type": "application/json"}
    if key:
        headers["authorization"] = f"Bearer {key}"
    with httpx.Client(timeout=180.0) as client:
        r = client.post(
            f"{base}/images/generations",
            headers=headers,
            json={"model": model, "prompt": prompt, "n": 1, "size": "1024x1024"},
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("data") or []
        if not items:
            raise RuntimeError(f"no image data: {data}")
        item = items[0]
        if item.get("b64_json"):
            import base64

            return base64.b64decode(item["b64_json"])
        url = item.get("url")
        if not url:
            raise RuntimeError(f"no url/b64 in image response: {item}")
        img = client.get(url)
        img.raise_for_status()
        return img.content


_SEND_FILE_OK = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".rtf", ".odt", ".ods", ".md",
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
}
_SEND_FILE_AV = {
    ".mp3", ".aac", ".m4a", ".wav", ".flac", ".ogg",
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v",
}


def _outbound_av_scan(path: Path, thread_id: str, name: str) -> str:
    """Scan generated file before Zalo. Returns clean|blocked|skip."""
    flag = (os.environ.get("AV_SCAN") or "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        print(f"[flow] stage=av_outbound_skip reason=disabled file={name}", flush=True)
        return "skip"
    required = (os.environ.get("AV_REQUIRED") or "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    av_url = (os.environ.get("AV_GATEWAY_URL") or "http://av-gateway:8098").rstrip("/")
    sec_url = (os.environ.get("SECURITY_URL") or "").rstrip("/")
    try:
        data = path.read_bytes()
    except OSError:
        return "skip" if not required else "blocked"
    if not data:
        return "skip"
    session_id = f"zalo-out-{uuid.uuid4().hex[:12]}"
    timeout = httpx.Timeout(45.0, connect=3.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            files = {"file": (name, data, "application/octet-stream")}
            form = {"session_id": session_id}
            if sec_url:
                try:
                    print(
                        f"[flow] stage=av_outbound_scan via=security file={name} thread_id={thread_id}",
                        flush=True,
                    )
                    r = client.post(f"{sec_url}/v1/scan", data=form, files=files)
                    if r.status_code < 300:
                        verdict = str((r.json() or {}).get("verdict") or "").lower()
                        if verdict in {"risk", "blocked", "infected"}:
                            return "blocked"
                        print(
                            f"[flow] stage=av_outbound_clean via=security file={name}",
                            flush=True,
                        )
                        return "clean"
                except Exception as e:  # noqa: BLE001
                    print(
                        f"[flow] stage=av_outbound_sec_fail file={name} error={type(e).__name__}",
                        flush=True,
                    )
            print(
                f"[flow] stage=av_outbound_scan via=av file={name} thread_id={thread_id}",
                flush=True,
            )
            r = client.post(f"{av_url}/v1/scan", data=form, files=files)
            if r.status_code >= 300:
                return "blocked" if required else "skip"
            for _ in range(40):
                r2 = client.get(f"{av_url}/v1/sessions/{session_id}/ready")
                if r2.status_code == 404:
                    break
                if r2.status_code >= 300:
                    time.sleep(0.4)
                    continue
                st = r2.json() or {}
                if st.get("blocked"):
                    return "blocked"
                if st.get("ready"):
                    print(
                        f"[flow] stage=av_outbound_clean via=av file={name}",
                        flush=True,
                    )
                    return "clean"
                time.sleep(0.4)
            return "blocked" if required else "skip"
    except Exception as e:  # noqa: BLE001
        print(
            f"[flow] stage=av_outbound_error file={name} error={type(e).__name__}",
            flush=True,
        )
        return "blocked" if required else "skip"


def _active_turn() -> dict[str, str]:
    """Zalo thread that asked this turn — never the sender's DM by mistake."""
    try:
        with httpx.Client(timeout=1.5) as c:
            r = c.get(f"{SESSION_URL}/v1/turn/dest")
            if r.status_code < 300:
                data = r.json() or {}
                tid = str(data.get("thread_id") or "").strip()
                tt = data.get("thread_type") if data.get("thread_type") in {"user", "group"} else ""
                if tid:
                    return {"thread_id": tid, "thread_type": tt or "user"}
    except Exception:
        pass
    return {}


def _claim_generated_file(path: Path, thread_id: str) -> bool:
    """True = this process may send. False = already sent this turn."""
    try:
        st = path.stat()
        key = f"{int(st.st_size)}:{path.name}"
    except OSError:
        return True
    try:
        with httpx.Client(timeout=1.5) as c:
            r = c.post(
                f"{SESSION_URL}/v1/files/claim",
                json={"key": key, "thread_id": thread_id},
            )
            if r.status_code < 300:
                return bool((r.json() or {}).get("first"))
    except Exception:
        pass
    return True


class SendFileReq(BaseModel):
    path: str
    thread_id: str
    thread_type: str = "user"
    caption: str = ""
    filename: Optional[str] = None
    lock_thread: bool = False


@app.post("/v1/send-file")
def send_file(req: SendFileReq) -> dict[str, Any]:
    """Send a generated office file to the Zalo requester. Refuse music/video."""
    raw = (req.path or "").strip()
    if not raw:
        raise HTTPException(400, "path required")
    dest = Path(raw)
    if not dest.is_file():
        alt = MEDIA_DIR / "out" / Path(raw).name
        if alt.is_file():
            dest = alt
    if not dest.is_file():
        raise HTTPException(404, f"file not found: {raw}")
    ext = dest.suffix.lower()
    if ext in _SEND_FILE_AV or not ext:
        raise HTTPException(400, "refuse music/video — use xlsx/docx/txt/pdf")
    if ext not in _SEND_FILE_OK:
        raise HTTPException(400, f"unsupported type {ext}")
    name = (req.filename or dest.name).strip() or dest.name
    staged = dest
    if dest.name != name:
        staged = MEDIA_DIR / "out" / name
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(dest.read_bytes())
    turn = {} if req.lock_thread else _active_turn()
    if turn.get("thread_id"):
        if req.thread_id and req.thread_id != turn["thread_id"]:
            print(
                f"[flow] stage=zalo_send_redirect from={req.thread_id} to={turn['thread_id']} "
                f"type={turn.get('thread_type')} file={name}",
                flush=True,
            )
        req.thread_id = turn["thread_id"]
        if turn.get("thread_type"):
            req.thread_type = turn["thread_type"]
    if not _claim_generated_file(staged, req.thread_id):
        print(
            f"[flow] stage=zalo_send_skip reason=already_sent file={name} thread_id={req.thread_id}",
            flush=True,
        )
        return {"ok": True, "file": name, "skipped": True, "reason": "already_sent"}
    t0 = time.time()
    scan = _outbound_av_scan(staged, req.thread_id, name)
    if scan == "blocked":
        print(
            f"[flow] stage=av_outbound_blocked thread_id={req.thread_id} file={name}",
            flush=True,
        )
        raise HTTPException(
            403,
            {
                "error": "av_blocked",
                "message": "File contains risks so it cannot be sent.",
            },
        )
    print(
        f"[flow] stage=zalo_send_file thread_id={req.thread_id} file={name} path={staged} av={scan}",
        flush=True,
    )
    zalo = _send_zalo_base64(req.thread_id, req.thread_type, staged, req.caption or "")
    _timing_add("workflow_s", time.time() - t0, req.thread_id)
    return {"ok": True, "file": name, "zalo": zalo, "av": scan}


def _send_zalo_base64(thread_id: str, thread_type: str, dest: Path, caption: str) -> dict[str, Any]:
    import base64

    bridge = os.environ.get("ZALO_BRIDGE_URL", "http://host.docker.internal:8787").rstrip("/")
    token = os.environ.get("ZALO_PLUGIN_TOKEN", "").strip()
    body = {
        "threadId": thread_id,
        "threadType": thread_type or "group",
        "caption": caption or "",
        "fileName": dest.name,
        "base64": base64.b64encode(dest.read_bytes()).decode("ascii"),
    }
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=90.0) as client:
        r = client.post(f"{bridge}/send-attachment", headers=headers, json=body)
        try:
            payload = r.json()
        except Exception:  # noqa: BLE001
            payload = {"raw": r.text[:500]}
        if r.status_code >= 400:
            raise HTTPException(502, {"error": "zalo send failed", "status": r.status_code, "body": payload})
        return payload if isinstance(payload, dict) else {"result": payload}


@app.post("/v1/image")
def image_generate(req: ImageReq) -> dict[str, Any]:
    """Image gen fallback (Medium+): llm → vendor → ComfyUI CPU → ComfyUI GPU.

    llm = OpenAI / Gemini / DeepSeek (IMAGE_LLM_PROVIDER).
    vendor = fal / pollinations / fluxai / ….
    Low: IMAGE_BACKENDS empty → 503.
    """
    from image_backends import generate_image_bytes, image_backends

    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(400, "prompt required")
    if not image_backends() and not (req.provider or "").strip():
        raise HTTPException(503, "image gen disabled (IMAGE_BACKENDS empty)")

    refine_meta: dict[str, Any] = {"refined": False}
    gen_prompt = prompt
    if req.refine and os.environ.get("IMAGE_REFINE", "1") != "0":
        gen_prompt, refine_meta = _refine_prompt_llm(prompt)

    name = req.filename or f"gen-{uuid.uuid4().hex[:10]}.jpg"
    if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        name += ".jpg"
    out_dir = MEDIA_DIR / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / name
    used = ""
    errors: list[str] = []
    raw: Optional[bytes] = None

    try:
        raw, used, errors = generate_image_bytes(gen_prompt, provider=req.provider)
        dest.write_bytes(raw)
    except Exception as e:  # noqa: BLE001
        # Optional pillow stub
        if (os.environ.get("IMAGE_ALLOW_PILLOW") or "0") == "1":
            try:
                _pillow_stub(gen_prompt if refine_meta.get("refined") else prompt, dest)
                used = "pillow"
                raw = dest.read_bytes()
                errors.append(str(e))
            except Exception as e2:  # noqa: BLE001
                raise HTTPException(502, {"error": "all image backends failed", "detail": [str(e), str(e2)]}) from e2
        else:
            raise HTTPException(502, {"error": "all image backends failed", "detail": str(e)}) from e

    if raw is None and not dest.is_file():
        raise HTTPException(502, {"error": "all image backends failed", "detail": errors})
    try:
        from PIL import Image

        img = Image.open(dest)
        if dest.suffix.lower() not in {".jpg", ".jpeg"}:
            jpg = dest.with_suffix(".jpg")
            img.convert("RGB").save(jpg, quality=90)
            dest = jpg
        elif img.mode != "RGB":
            img.convert("RGB").save(dest, quality=90)
    except Exception:  # noqa: BLE001
        pass
    hermes_path = f"/opt/data/media/out/{dest.name}"
    result: dict[str, Any] = {
        "ok": True,
        "provider": used,
        "backends": image_backends(),
        "prompt_original": prompt,
        "prompt_used": gen_prompt,
        "refine": refine_meta,
        "file": str(dest),
        "hermes_path": hermes_path,
        "errors": errors,
    }
    if req.send_zalo:
        if not req.thread_id:
            raise HTTPException(400, "thread_id required when send_zalo=true")
        result["zalo"] = _send_zalo_base64(
            req.thread_id, req.thread_type, dest, req.caption or prompt[:80]
        )
    return result


from office_file import register_office_file

register_office_file(
    app,
    MEDIA_DIR,
    lambda **kw: send_file(SendFileReq(**kw)),
)
