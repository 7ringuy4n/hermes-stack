"""Read images and scanned PDFs via model-router combo vision-ocr."""
from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from vision_refuse import llm_refused, vision_chunk_usable, vision_text_echoes_prompt

API_KEY = (
    os.environ.get("OPENAI_API_KEY")
    or os.environ.get("OMNIROUTER_API_KEY")
    or os.environ.get("OCR_API_KEY")
    or ""
).strip()


def _chat_base() -> str:
    raw = (
        os.environ.get("HERMES_OPENAI_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("MODEL_ROUTER_URL")
        or "http://model-router:8096"
    ).rstrip("/")
    if not raw.endswith("/v1"):
        raw = f"{raw}/v1"
    return raw


def _describe_model() -> str:
    """Scene describe always uses vision-ocr combo (never chat-only hermes)."""
    m = (os.environ.get("OCR_MODEL") or os.environ.get("OPENAI_MODEL") or "vision-ocr").strip()
    return "vision-ocr" if m.lower() == "hermes" else (m or "vision-ocr")


BASE = _chat_base()
MODEL = os.environ.get("OCR_MODEL") or os.environ.get("OPENAI_MODEL") or "vision-ocr"
MEDIA_ROOT = Path(os.environ.get("OCR_MEDIA_ROOT") or os.environ.get("INGEST_MEDIA_ROOT") or "/data/media")

_MEDIA_PREFIXES = (
    "/opt/data/media/",
    "/data/assistant/media/",
    "/data/media/",
    "opt/data/media/",
    "data/assistant/media/",
    "data/media/",
)


def _media_roots() -> tuple[Path, ...]:
    seen: set[str] = set()
    roots: list[Path] = []
    for raw in (
        os.environ.get("OCR_MEDIA_ROOT"),
        os.environ.get("INGEST_MEDIA_ROOT"),
        str(MEDIA_ROOT),
        "/opt/data/media",
        "/opt/data",
        "/data/media",
        "/data/assistant/media",
    ):
        if not raw:
            continue
        key = str(raw).replace("\\", "/").rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        roots.append(Path(key))
    return tuple(roots)


def resolve_media_path(raw: Optional[str]) -> Optional[Path]:
    if not raw:
        return None
    s = str(raw).strip().replace("\\", "/")
    candidates: list[Path] = [Path(s)]
    # Hermes bind: host /data/assistant → container /opt/data
    if s.startswith("/data/assistant/"):
        candidates.append(Path("/opt/data") / s[len("/data/assistant/") :])
    elif s.startswith("/opt/data/"):
        candidates.append(Path("/data/assistant") / s[len("/opt/data/") :])
    if "/replicas/" in s and not s.startswith("/opt/data/"):
        candidates.append(Path("/opt/data") / s.lstrip("/"))
    rel: str | None = None
    for prefix in _MEDIA_PREFIXES:
        if s.startswith(prefix):
            rel = Path(s[len(prefix) :]).as_posix()
            break
    if rel:
        for root in _media_roots():
            candidates.append(root / rel)
    elif not Path(s).is_absolute():
        for root in _media_roots():
            candidates.append(root / s.lstrip("/"))
    seen: set[str] = set()
    for p in candidates:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


MIN_TEXT = int(os.environ.get("OCR_MIN_CHARS", "8"))
VISION_MAX_PX = int(os.environ.get("OCR_VISION_MAX_PX", "1536"))
VISION_TRIP_AFTER = int(os.environ.get("OCR_VISION_TRIP_AFTER", "3"))
VISION_COOLDOWN_S = float(os.environ.get("OCR_VISION_COOLDOWN_S", "900"))

DEFAULT_PROMPT = "Describe this image naturally and include any text visible in it."

DESCRIBE_SYSTEM = (
    "You describe photographs for chat users. Write complete sentences about the "
    "overall scene, main subjects, setting, lighting, and mood. Include visible text "
    "only inside sentences — never output isolated OCR tokens, label lists, or "
    "single-word-per-line dumps."
)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif"}

_vision_state: dict[str, float] = {"refusals": 0.0, "blind_until": 0.0}


def pymupdf_text(path: Path) -> str:
    import pymupdf

    doc = pymupdf.open(path)
    parts: list[str] = []
    try:
        for page in doc:
            t = page.get_text("text") or ""
            if t.strip():
                parts.append(t.strip())
    finally:
        doc.close()
    return "\n\n".join(parts).strip()


def pymupdf_page_jpegs(path: Path, *, max_pages: int = 4) -> list[bytes]:
    import pymupdf

    out: list[bytes] = []
    doc = pymupdf.open(path)
    try:
        n = min(len(doc), max_pages)
        for i in range(n):
            pix = doc[i].get_pixmap(dpi=150)
            out.append(pix.tobytes("jpeg"))
    finally:
        doc.close()
    return out


def resize_jpeg_bytes(data: bytes, *, max_px: int = VISION_MAX_PX) -> tuple[bytes, str]:
    try:
        from PIL import Image
    except ImportError:
        return data, "image/jpeg"
    try:
        im = Image.open(io.BytesIO(data))
        im = im.convert("RGB")
        w, h = im.size
        scale = min(1.0, float(max_px) / float(max(w, h)))
        if scale < 1.0:
            im = im.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except OSError:
        return data, "image/jpeg"


def vision_b64_from_bytes(data: bytes, mime: str = "image/jpeg") -> tuple[str, str]:
    if mime.lower().endswith("png") or data[:8] == b"\x89PNG\r\n\x1a\n":
        jpeg, mime_out = resize_jpeg_bytes(data)
        return base64.b64encode(jpeg).decode("ascii"), mime_out
    if len(data) > 400_000:
        jpeg, mime_out = resize_jpeg_bytes(data)
        return base64.b64encode(jpeg).decode("ascii"), mime_out
    return base64.b64encode(data).decode("ascii"), mime


def vision_b64_from_path(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return vision_b64_from_bytes(raw, mime)


def _vision_ready() -> bool:
    return time.time() >= _vision_state["blind_until"]


def _vision_note(refused: bool, *, status: int = 200) -> None:
    # Infra / config errors must not trigger the 15m vision cooldown.
    if status in (0,) or status >= 500:
        return
    if not refused:
        _vision_state["refusals"] = 0.0
        _vision_state["blind_until"] = 0.0
        return
    _vision_state["refusals"] += 1
    if _vision_state["refusals"] >= VISION_TRIP_AFTER:
        _vision_state["blind_until"] = time.time() + VISION_COOLDOWN_S
        _vision_state["refusals"] = 0.0


def _http_post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    timeout: float = 180,
) -> tuple[int, str]:
    # Full body required — truncating before json.loads drops Vietnamese descriptions.
    if httpx is not None:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, headers=headers, json=payload)
            return r.status_code, r.text
    import urllib.error
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return int(e.code), raw


def _vision_chat(
    b64: str,
    mime: str,
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 512,
) -> tuple[int, str, str]:
    base = _chat_base()
    key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OMNIROUTER_API_KEY")
        or os.environ.get("OCR_API_KEY")
        or ""
    ).strip()
    use_model = (model or MODEL or "vision-ocr").strip()
    if not key or not base:
        return 0, "vision_not_configured", ""
    try:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        )
        status, body = _http_post_json(
            f"{base}/chat/completions",
            {"Authorization": f"Bearer {key}"},
            {
                "model": use_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.2,
                "metadata": {"task_hint": "file", "task_type": "file_processing"},
            },
        )
        text = ""
        if status < 400:
            try:
                payload = json.loads(body)
                choices = payload.get("choices") if isinstance(payload, dict) else None
                if isinstance(choices, list) and choices:
                    ch = choices[0] if isinstance(choices[0], dict) else {}
                    msg = ch.get("message") if isinstance(ch.get("message"), dict) else {}
                    for key_name in (
                        "content",
                        "reasoning_content",
                        "reasoning",
                        "thinking",
                        "thinking_content",
                    ):
                        val = msg.get(key_name)
                        if isinstance(val, str) and val.strip():
                            text = val.strip()
                            break
                    if not text and isinstance(ch.get("text"), str):
                        text = ch["text"].strip()
            except Exception:
                text = ""
        # Truncate only for log/detail — content already extracted above.
        return status, (body or "")[:800], (text or "").strip()
    except Exception as e:
        return 0, type(e).__name__, ""


def _describe_chunk_ok(chunk: str, prompt: str, *, min_chars: int) -> bool:
    echo_ref = f"{prompt}\n{DESCRIBE_SYSTEM}"
    return (
        bool(chunk)
        and vision_chunk_usable(chunk, min_chars=min_chars)
        and not vision_text_echoes_prompt(chunk, echo_ref)
    )


def vision_read_bytes(data: bytes, prompt: str = DEFAULT_PROMPT, *, mime: str = "image/jpeg") -> str:
    if not _vision_ready():
        return ""
    b64, out_mime = vision_b64_from_bytes(data, mime)
    status, body, chunk = _vision_chat(b64, out_mime, prompt)
    refused = llm_refused(status, body, chunk) or not chunk
    _vision_note(refused, status=status)
    if chunk and not llm_refused(status, body, chunk) and _describe_chunk_ok(chunk, prompt, min_chars=MIN_TEXT):
        return chunk
    return ""


def vision_read_path(path: str | Path, prompt: str = DEFAULT_PROMPT) -> str:
    p = resolve_media_path(str(path)) or Path(str(path))
    if not p.is_file():
        return ""
    low = p.suffix.lower()
    if low == ".pdf":
        try:
            text = pymupdf_text(p)
        except Exception:
            text = ""
        if len(text) >= MIN_TEXT:
            return text
        parts: list[str] = []
        for jpeg in pymupdf_page_jpegs(p):
            chunk = vision_read_bytes(jpeg, prompt, mime="image/jpeg")
            if chunk:
                parts.append(chunk)
        return "\n\n".join(parts).strip()
    if low not in IMAGE_EXTS:
        return ""
    b64, mime = vision_b64_from_path(p)
    if not _vision_ready():
        return ""
    status, body, chunk = _vision_chat(b64, mime, prompt)
    refused = llm_refused(status, body, chunk) or not chunk
    _vision_note(refused, status=status)
    if chunk and not llm_refused(status, body, chunk) and _describe_chunk_ok(chunk, prompt, min_chars=MIN_TEXT):
        return chunk
    return ""


def vision_read(
    *,
    path: Optional[str] = None,
    image_b64: Optional[str] = None,
    prompt: str = DEFAULT_PROMPT,
) -> dict[str, Any]:
    """Unified read API for images and PDFs."""
    if path:
        text = vision_read_path(path, prompt)
        if text:
            return {"ok": True, "text": text, "via": "vision-ocr"}
        return {"ok": True, "text": "", "via": "vision-ocr", "empty": True}
    if image_b64:
        raw = base64.b64decode(image_b64)
        text = vision_read_bytes(raw, prompt)
        if text:
            return {"ok": True, "text": text, "via": "vision-ocr"}
        return {"ok": True, "text": "", "via": "vision-ocr", "empty": True}
    return {"ok": False, "error": "path or image_b64 required", "via": "vision-ocr"}


def vision_describe(
    *,
    path: Optional[str] = None,
    image_b64: Optional[str] = None,
    prompt: str = DEFAULT_PROMPT,
    min_chars: int = 8,
) -> dict[str, Any]:
    """Host scene describe — no cooldown; always vision-ocr combo."""
    try:
        if path:
            p = resolve_media_path(str(path))
            if p is None or not p.is_file():
                return {
                    "ok": False,
                    "text": "",
                    "via": "vision-ocr",
                    "error": "path_not_found",
                    "path": str(path),
                }
            b64, mime = vision_b64_from_path(p)
        elif image_b64:
            raw = base64.b64decode(image_b64)
            b64, mime = vision_b64_from_bytes(raw)
        else:
            return {"ok": False, "error": "path or image_b64 required", "via": "vision-ocr"}
        attempts = max(
            1, min(int(os.environ.get("OCR_VISION_ROTATE_ATTEMPTS", "3")), 5)
        )
        last_status = 0
        last_body = ""
        last_chunk = ""
        for _ in range(attempts):
            status, body, chunk = _vision_chat(
                b64,
                mime,
                prompt,
                model=_describe_model(),
                system=DESCRIBE_SYSTEM,
                max_tokens=512,
            )
            last_status, last_body, last_chunk = status, body, chunk
            if (
                chunk
                and not llm_refused(status, body, chunk)
                and _describe_chunk_ok(chunk, prompt, min_chars=min_chars)
            ):
                return {
                    "ok": True,
                    "text": chunk,
                    "via": "vision-ocr",
                    "model": _describe_model(),
                    "status": status,
                }
        return {
            "ok": False,
            "text": last_chunk or "",
            "via": "vision-ocr",
            "empty": not last_chunk,
            "model": _describe_model(),
            "status": last_status,
            "detail": (last_body or "")[:240],
            "error": (
                "vision_refused"
                if llm_refused(last_status, last_body, last_chunk)
                else (
                    "vision_echo"
                    if last_chunk
                    and vision_text_echoes_prompt(
                        last_chunk, f"{prompt}\n{DESCRIBE_SYSTEM}"
                    )
                    else "vision_empty"
                )
            ),
        }
    except Exception as e:
        return {"ok": False, "text": "", "via": "vision-ocr", "error": type(e).__name__}


def empty_scan_result(via: str) -> dict[str, Any]:
    """Local vision read finished; the image simply has no readable content."""
    return {"ok": True, "text": "", "via": via or "none", "empty": True}
