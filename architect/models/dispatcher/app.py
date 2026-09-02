"""assistant Media/File worker — media download, convert, image/video, ASR, OCR text.

Web search moved to the Router Worker (`model-router /v1/search`) so vendor HTTP
never competes with media work here. Heavy endpoints stay sync (threadpool);
`/health` is async so probes cannot flap while media jobs run.
"""
from __future__ import annotations

import itertools
import os
import shutil
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

from image_backends import image_backends
from video_summary import health_fields, omni_refuse_message, policy_block_response, register_video_summary

app = FastAPI(title="assistant dispatcher", version="1.1.0")

SESSION_URL = os.environ.get("SESSION_URL", "http://session:8107").rstrip("/")
N9_UPSTREAM = os.environ.get("OPENAI_BASE_URL", "http://omni-router:20129/v1").rstrip("/")
_MSG_PATH = Path(
    os.environ.get(
        "DISPATCHER_MESSAGES_FILE",
        str(Path(__file__).resolve().parent / "messages" / "en.json"),
    )
)


def _load_messages() -> dict[str, str]:
    try:
        import json as _json

        return _json.loads(_MSG_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {
            "image_gen_disabled": "Image generation is unavailable (no media backends configured).",
            "office_gen_disabled": "Office file generation is unavailable.",
            "web_search_disabled": "Web search is unavailable (no search backends configured).",
            "web_extract_disabled": "Web extract is unavailable (no search backends configured).",
            "prompt_required": "A prompt is required.",
            "media_gen_failed": "Could not generate media. Try a simpler request or try again later.",
        }


MESSAGES = _load_messages()


def _msg(key: str, fallback: str) -> str:
    return str(MESSAGES.get(key) or fallback)


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

# Web search lives on the Router Worker (model-router /v1/search) so the media
# worker never blocks on vendor HTTP. Kept only to advertise the route.
WEB_SEARCH_URL = (
    os.environ.get("WEB_SEARCH_URL")
    or os.environ.get("MODEL_ROUTER_URL")
    or "http://router-worker:8096"
).rstrip("/")


def _key(name: str) -> str:
    return os.environ.get(f"{name.upper()}_API_KEY", "").strip()


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
    provider: Optional[str] = None  # omni|n9|text|info-card
    mode: Optional[str] = None  # text|poster → exact glyph poster, skip diffusion
    size: Optional[str] = None  # optional; skill declares HD default (1920x1080, 16:9)
    poster_n: Optional[int] = None
    poster_phrase: Optional[str] = None
    poster_bw: Optional[bool] = None
    thread_id: Optional[str] = None
    thread_type: str = "group"
    send_zalo: bool = False
    caption: str = ""
    refine: bool = True  # DeepSeek/LLM rewrite prompt before gen; wait for reply
    overlay: Optional[list[str]] = None  # short fact lines already fetched by the agent


class VideoReq(BaseModel):
    """Short H.264 clip from a still (dispatcher default — not Hermes-invented tools)."""
    prompt: Optional[str] = None
    image: Optional[str] = None  # existing file under media/out
    filename: Optional[str] = None
    seconds: float = 4.0
    overlay: Optional[list[str]] = None
    refine: bool = False
    provider: Optional[str] = None


@app.get("/health")
async def health() -> dict[str, Any]:
    """Async so a saturated media threadpool cannot flap the health probe."""
    return {
        "ok": True,
        "web_search": WEB_SEARCH_URL,
        "keys": {
            "deepseek": bool(
                os.environ.get("DEEPSEEK_API_KEY")
                or os.environ.get("DEEPSEEK_OCR_API_KEY")
                or ""
            ),
            "n9router": bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("N9ROUTER_API_KEY") or ""),
        },
        "media_dir": str(MEDIA_DIR),
        "image_backends": image_backends(),
        "image_gen_combo": os.environ.get("IMAGE_GEN_COMBO") or "image-gen",
        "image_provider": os.environ.get("IMAGE_PROVIDER", ""),
        "zalo_bridge": bool(os.environ.get("ZALO_BRIDGE_URL", "").strip()),
        "whisper_model": os.environ.get("WHISPER_MODEL", "tiny"),
        "whisper_enabled": os.environ.get("WHISPER_ENABLED", "1") != "0",
        **health_fields(MEDIA_DIR),
    }


@app.post("/v1/mode")
def mode_switch(req: ModeReq) -> dict[str, Any]:
    """Return which skill/mode Hermes should prefer (soft switch, not slash-required)."""
    m = req.mode.strip().lower()
    if m not in {"chat", "research", "upload", "code", "auto"}:
        raise HTTPException(400, "mode must be chat|research|upload|code|auto")
    if m == "auto":
        m = "upload" if req.has_media else "chat"
    hints = {
        "chat": "Use skill chat + common-rules.",
        "research": "Use skill research; web via model-router /v1/search.",
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
    text = " ".join(" ".join(parts).split()).strip()
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


VIDEO_TEXT_EXTS = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi"}
AUDIO_TEXT_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac"}
MEDIA_TEXT_FRAMES = int(os.environ.get("MEDIA_TEXT_FRAMES", "4"))
MEDIA_TEXT_FRAME_TIMEOUT_S = float(os.environ.get("MEDIA_TEXT_FRAME_TIMEOUT_S", "40"))
OCR_URL = (os.environ.get("OCR_URL") or "http://ocr:8091").rstrip("/")


class MediaTextReq(BaseModel):
    """Readable text for audio/video so the agent can summarize before replying."""

    path: str
    language: Optional[str] = None
    frames: int = MEDIA_TEXT_FRAMES


def _media_duration_s(src: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        done = subprocess.run(
            [
                ffprobe, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(src),
            ],
            check=True,
            capture_output=True,
            timeout=MEDIA_TEXT_FRAME_TIMEOUT_S,
        )
        return max(0.0, float((done.stdout or b"").decode("utf-8", "replace").strip() or 0))
    except Exception:  # noqa: BLE001
        return 0.0


def _video_keyframes(src: Path, frames: int) -> list[Path]:
    """Evenly spaced JPEG stills next to the source.

    Seeks to explicit timestamps instead of an fps filter so that a clip
    shorter than the sampling interval still yields a frame.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return []
    n = max(1, min(int(frames or MEDIA_TEXT_FRAMES), 8))
    duration = _media_duration_s(src)
    if duration <= 0:
        stamps = [0.0]
    else:
        stamps = [duration * (i + 0.5) / n for i in range(n)]
    out_dir = src.parent / f".frames-{src.stem}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for idx, ts in enumerate(stamps):
        dest = out_dir / f"frame-{idx:02d}.jpg"
        try:
            subprocess.run(
                [
                    ffmpeg, "-y", "-ss", f"{ts:.3f}", "-i", str(src),
                    "-frames:v", "1", "-q:v", "4", str(dest),
                ],
                check=True,
                capture_output=True,
                timeout=MEDIA_TEXT_FRAME_TIMEOUT_S,
            )
        except Exception:  # noqa: BLE001
            continue
        if dest.is_file() and dest.stat().st_size > 0:
            out.append(dest)
    return out


def _ocr_file(path: Path) -> str:
    try:
        with httpx.Client(timeout=90.0) as client:
            r = client.post(
                f"{OCR_URL}/v1/ocr",
                json={"path": str(path), "prompt": "Extract all visible text as markdown."},
            )
            if r.status_code >= 300:
                return ""
            data = r.json()
    except Exception:  # noqa: BLE001
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("text") or data.get("markdown") or "").strip()


@app.post("/v1/media/text")
def media_text(req: MediaTextReq) -> dict[str, Any]:
    """Transcript (audio track) + on-screen text (keyframe OCR) for one media file."""
    src = Path(req.path)
    if not src.is_file():
        raise HTTPException(400, f"path not found: {req.path}")
    ext = src.suffix.lower()
    if ext not in VIDEO_TEXT_EXTS | AUDIO_TEXT_EXTS:
        raise HTTPException(415, f"unsupported media type: {ext or 'unknown'}")
    transcript = ""
    transcript_error = ""
    try:
        transcript = _whisper_transcribe(src, req.language)
    except Exception as e:  # noqa: BLE001 — ASR is optional (WHISPER_ENABLED)
        transcript_error = str(e)[:200]
    frame_text: list[str] = []
    frames_read = 0
    if ext in VIDEO_TEXT_EXTS:
        keyframes = _video_keyframes(src, req.frames)
        frames_read = len(keyframes)
        for frame in keyframes:
            hit = _ocr_file(frame)
            if hit:
                frame_text.append(hit)
            try:
                frame.unlink()
            except OSError:
                pass
        if keyframes:
            try:
                keyframes[0].parent.rmdir()
            except OSError:
                pass
    parts: list[str] = []
    if transcript:
        parts.append(f"## Transcript\n{transcript}")
    if frame_text:
        parts.append("## On-screen text\n" + "\n\n".join(frame_text))
    text = "\n\n".join(parts).strip()
    return {
        "ok": bool(text),
        "file": str(src),
        "text": text,
        "transcript": transcript,
        "frames_read": frames_read,
        "frames_with_text": len(frame_text),
        "error": transcript_error if not text else "",
    }



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
        suf = path.suffix.lower()
        if suf in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            key = f"img:{(path.stem or path.name).lower()}"
        else:
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


def _send_zalo_attachment(thread_id: str, thread_type: str, dest: Path, caption: str) -> dict[str, Any]:
    """Send via hermes-zalo-plugin /send-attachment (requires host filesystem paths)."""
    bridge = (
        os.environ.get("ZALO_BRIDGE_URL")
        or os.environ.get("ZALO_PLUGIN_URL")
        or "http://zalo-proxy:8787"
    ).rstrip("/")
    token = os.environ.get("ZALO_PLUGIN_TOKEN", "").strip()
    host_media = (
        os.environ.get("ZALO_HOST_MEDIA_DIR")
        or os.environ.get("ZALO_HOST_DATA_DIR", "/data/assistant") + "/media"
    ).rstrip("/")
    try:
        rel = dest.resolve().relative_to(MEDIA_DIR.resolve())
        host_path = str(Path(host_media) / rel)
    except Exception:  # noqa: BLE001
        # Fallback: /data/media/out/x → /data/assistant/media/out/x
        host_path = str(dest).replace("/data/media", host_media, 1)
    body = {
        "threadId": thread_id,
        "threadType": thread_type or "user",
        "caption": caption or "",
        "paths": [host_path],
        "path": host_path,
        "fileName": dest.name,
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


def _send_zalo_base64(thread_id: str, thread_type: str, dest: Path, caption: str) -> dict[str, Any]:
    """Back-compat alias — bridge no longer accepts base64."""
    return _send_zalo_attachment(thread_id, thread_type, dest, caption)


def _apply_image_overlay(dest: Path, lines) -> int:
    """Retired Pillow overlay layout — facts belong in the Omni diffusion prompt."""
    del dest, lines
    return 0


def _chown_media(path: Path) -> None:
    try:
        uid = int(os.environ.get("HERMES_UID") or "1000")
        gid = int(os.environ.get("HERMES_GID") or str(uid))
        os.chown(path.parent, uid, gid)
        os.chown(path, uid, gid)
    except OSError:
        pass


@app.post("/v1/image")
def image_generate(req: ImageReq) -> dict[str, Any]:
    """Pillow text-poster only. Scenic / labeled stills → Omni combo image-gen.
    """
    from text_poster import parse_text_poster, render_text_poster_bytes

    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(400, _msg("prompt_required", "A prompt is required."))

    mode = (req.mode or req.provider or "").strip().lower()
    poster = parse_text_poster(
        prompt,
        phrase=str(req.poster_phrase or ""),
        n=req.poster_n,
        bw=req.poster_bw,
    )
    if mode in {"text", "poster", "text-poster"} and not poster:
        poster = {"phrase": prompt[:80], "n": 1, "bw": True, "raw": prompt}
    if poster:
        name = req.filename or f"text-{uuid.uuid4().hex[:10]}.png"
        if not name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            name += ".png"
        out_dir = MEDIA_DIR / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / name
        dest.write_bytes(render_text_poster_bytes(poster))
        try:
            uid = int(os.environ.get("HERMES_UID") or "1000")
            gid = int(os.environ.get("HERMES_GID") or str(uid))
            os.chown(out_dir, uid, gid)
            os.chown(dest, uid, gid)
        except OSError:
            pass
        return {
            "ok": True,
            "file": name,
            "path": str(dest),
            "backend": "text-poster",
            "n": poster["n"],
            "phrase": poster["phrase"],
        }

    if mode in {"info-card", "card", "infocard", "weather-card", "overlay"} or "TITLE:" in prompt.upper():
        raise HTTPException(
            410,
            {
                "error": "pillow_layout_retired",
                "detail": (
                    "Pillow info-card/overlay layout is removed. "
                    "Use OmniRouter POST /v1/images/generations with model image-gen "
                    "(combo image-gen); put labels/facts in the English SCENE prompt."
                ),
            },
        )

    raise HTTPException(
        410,
        {
            "error": "diffusion_moved_to_omni",
            "detail": (
                "POST /v1/image no longer runs diffusion. "
                "Use OmniRouter POST /v1/images/generations with model image-gen. "
                "Pillow mode remaining: mode=text-poster (alias /v1/text-poster)."
            ),
        },
    )


@app.post("/v1/info-card")
def info_card_generate(req: ImageReq) -> dict[str, Any]:
    """Retired — use Omni combo image-gen with facts in the SCENE prompt."""
    raise HTTPException(
        410,
        {
            "error": "info_card_retired",
            "detail": (
                "Pillow info-card removed. POST OmniRouter /v1/images/generations "
                "model=image-gen with an English SCENE prompt that includes labels/facts."
            ),
        },
    )


@app.post("/v1/text-poster")
def text_poster_generate(req: ImageReq) -> dict[str, Any]:
    """Pillow exact-text poster (not Omni diffusion)."""
    req.mode = "text-poster"
    return image_generate(req)


@app.post("/v1/overlay")
def image_overlay(req: ImageReq) -> dict[str, Any]:
    """Retired — bake overlay facts into the Omni image-gen SCENE prompt instead."""
    raise HTTPException(
        410,
        {
            "error": "overlay_retired",
            "detail": (
                "Pillow /v1/overlay removed. Include weather/metric lines in the "
                "Omni combo image-gen SCENE prompt (classify/image-gen skills)."
            ),
        },
    )


@app.post("/v1/video")
def video_generate(req: VideoReq) -> dict[str, Any]:
    """Video generation blocked — same policy as video-summary; OmniRouter writes refuse text."""
    ctx = (req.prompt or req.image or req.filename or "").strip()
    message, meta = omni_refuse_message(topic="video_generate", context=ctx)
    return policy_block_response(reason="video_policy", message=message, meta=meta)


class RemuxReq(BaseModel):
    filename: str


@app.post("/v1/video-remux")
def video_remux(req: RemuxReq) -> dict[str, Any]:
    """Re-encode an existing clip in media/out to Zalo-safe H.264."""
    from video_clip import ffmpeg_bin, remux_mp4

    name = Path(str(req.filename or "").strip()).name
    if not name:
        raise HTTPException(400, "filename required")
    src = (MEDIA_DIR / "out") / name
    if not src.is_file():
        raise HTTPException(404, f"missing {name}")
    if not ffmpeg_bin():
        raise HTTPException(503, "ffmpeg missing — cannot encode video")
    dest = src.with_name(src.stem + ".zalo.mp4")
    try:
        remux_mp4(src, dest)
        _chown_media(dest)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, {"error": "video remux failed", "detail": str(e)}) from e
    return {"ok": True, "file": str(dest), "hermes_path": f"/opt/data/media/out/{dest.name}"}


from office_file import register_office_file

register_office_file(
    app,
    MEDIA_DIR,
    lambda **kw: send_file(SendFileReq(**kw)),
)
