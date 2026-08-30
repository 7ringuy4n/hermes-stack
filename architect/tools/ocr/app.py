"""OCR — PaddleOCR first for all docs; vision-ocr combo fallback; tesseract last.

Pipeline: pymupdf text layer (PDF) → PaddleOCR → vision combo (OCR_MODEL, default
vision-ocr via Omni/9Router chat multimodal) → tesseract.
"""
from __future__ import annotations

import base64
import io
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from refuse import llm_refused as _llm_refused
from result import empty_scan_result as _empty_ok
import paddle_engine

API_KEY = (
    os.environ.get("OPENAI_API_KEY")
    or os.environ.get("OMNIROUTER_API_KEY")
    or os.environ.get("N9ROUTER_API_KEY")
    or os.environ.get("OCR_API_KEY")
    or ""
).strip()
BASE = os.environ.get("OPENAI_BASE_URL", "http://omni-router:20129/v1").rstrip("/")
MODEL = os.environ.get("OCR_MODEL") or os.environ.get("OPENAI_MODEL") or "vision-ocr"
MEDIA_ROOT = Path(os.environ.get("OCR_MEDIA_ROOT", "/data/media"))
FALLBACK = (os.environ.get("OCR_FALLBACK") or "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
# Vision combo after Paddle. Default on so scanned docs still get text.
VISION = (os.environ.get("OCR_VISION") or "active").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
    "active",
}
MIN_TEXT = int(os.environ.get("OCR_MIN_CHARS", "8"))
VISION_TRIP_AFTER = int(os.environ.get("OCR_VISION_TRIP_AFTER", "3"))
VISION_COOLDOWN_S = float(os.environ.get("OCR_VISION_COOLDOWN_S", "900"))

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
DOC_EXTS = IMAGE_EXTS | {".pdf"}

app = FastAPI(title="assistant-ocr", version="1.4.0")


def _flow(stage: str, **fields: Any) -> None:
    parts = [f"[flow] stage={stage}"]
    for k, v in fields.items():
        if v is None:
            continue
        s = str(v).replace("\n", " ").replace('"', "'")
        if " " in s:
            s = f'"{s}"'
        parts.append(f"{k}={s}")
    print(" ".join(parts), flush=True)


def _text_usable(text: str) -> bool:
    """True when OCR text is clear enough to skip vision fallback (no regex)."""
    body = (text or "").strip()
    if len(body) < MIN_TEXT:
        return False
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return False
    if len(lines) >= 3:
        short = sum(1 for ln in lines if len(ln) <= 1)
        if short / len(lines) >= 0.6:
            return False
    words = [w for w in body.replace("\n", " ").split() if len(w) >= 2]
    if len(body) >= 12 and len(words) <= 1 and len(lines) >= 4:
        return False
    return True


class OcrReq(BaseModel):
    path: Optional[str] = None
    image_b64: Optional[str] = None
    prompt: str = Field(
        default="Analyze this file. Describe visible content and extract any readable text as markdown. Preserve tables if present."
    )


@app.get("/health")
def health() -> dict[str, Any]:
    tess = False
    try:
        import shutil

        tess = bool(shutil.which("tesseract"))
    except Exception:
        tess = False
    return {
        "ok": True,
        "engine": "paddle" if paddle_engine.available() else "local",
        "primary": "paddle",
        "vision": VISION,
        "model": MODEL,
        "via": "paddle",
        "configured": bool(API_KEY and BASE),
        "fallback": FALLBACK,
        "tesseract": tess,
        **paddle_engine.ready(),
    }


def _resolve_path(raw: Optional[str]) -> Optional[Path]:
    if not raw:
        return None
    s = str(raw).strip()
    for prefix in (
        "/opt/data/media/",
        "/data/assistant/media/",
        "opt/data/media/",
        "data/assistant/media/",
    ):
        if s.startswith(prefix) or s.replace("\\", "/").startswith(prefix):
            s = str(MEDIA_ROOT / Path(s[len(prefix) :]).as_posix())
            break
    p = Path(s)
    if not p.is_absolute():
        p = MEDIA_ROOT / s.lstrip("/")
    return p if p.is_file() else None


def _pymupdf_text(path: Path) -> str:
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


def _pymupdf_page_jpegs(path: Path, *, max_pages: int = 4) -> list[bytes]:
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


def _tesseract_bytes(data: bytes) -> str:
    import shutil

    if not shutil.which("tesseract"):
        return ""
    from PIL import Image
    import pytesseract

    im = Image.open(io.BytesIO(data))
    if im.mode not in {"RGB", "L"}:
        im = im.convert("RGB")
    return (pytesseract.image_to_string(im, lang="vie+eng") or "").strip()


_vision_state: dict[str, float] = {"refusals": 0.0, "blind_until": 0.0}


def _vision_ready() -> bool:
    return VISION and time.time() >= _vision_state["blind_until"]


def _vision_note(refused: bool) -> None:
    if not refused:
        _vision_state["refusals"] = 0.0
        _vision_state["blind_until"] = 0.0
        return
    _vision_state["refusals"] += 1
    if _vision_state["refusals"] >= VISION_TRIP_AFTER:
        _vision_state["blind_until"] = time.time() + VISION_COOLDOWN_S
        _vision_state["refusals"] = 0.0
        _flow("vision_cooldown", model=MODEL, seconds=int(VISION_COOLDOWN_S))


def _vision(b64: str, mime: str, prompt: str) -> tuple[int, str, str]:
    if not API_KEY or not BASE:
        return 0, "ocr_not_configured", ""
    try:
        with httpx.Client(timeout=180) as c:
            r = c.post(
                f"{BASE}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={
                    "model": MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                                },
                            ],
                        }
                    ],
                },
            )
        body = r.text[:800]
        text = ""
        if r.status_code < 400:
            try:
                text = (
                    r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    or ""
                )
            except Exception:
                text = ""
        return r.status_code, body, (text or "").strip()
    except Exception as e:
        return 0, type(e).__name__, ""


def _paddle_image(path: Optional[Path], image_b64: Optional[str]) -> tuple[str, str]:
    """(text, error) — primary path for screenshots / receipts / UI."""
    return paddle_engine.extract_text(path=path, image_b64=image_b64)


def _tesseract_local(path: Optional[Path], image_b64: Optional[str]) -> tuple[str, str]:
    if path and path.suffix.lower() == ".pdf":
        text = _pymupdf_text(path)
        if len(text) >= MIN_TEXT:
            return text, "pymupdf"
        chunks: list[str] = []
        for jpeg in _pymupdf_page_jpegs(path):
            t = _tesseract_bytes(jpeg)
            if t:
                chunks.append(t)
        if chunks:
            return "\n\n".join(chunks), "tesseract+pymupdf"
        return text, "pymupdf"
    data: Optional[bytes] = None
    if image_b64:
        data = base64.b64decode(image_b64)
    elif path:
        data = path.read_bytes()
    if data:
        t = _tesseract_bytes(data)
        if t:
            return t, "tesseract"
    return "", "none"


def _paddle_pdf_pages(path: Path) -> tuple[str, str]:
    """OCR rasterized PDF pages with Paddle when there is no text layer."""
    pages: list[str] = []
    err = ""
    for jpeg in _pymupdf_page_jpegs(path):
        b64 = base64.b64encode(jpeg).decode("ascii")
        text, e = _paddle_image(None, b64)
        if e and not err:
            err = e
        if text:
            pages.append(text)
    return ("\n\n".join(pages).strip(), err)


@app.post("/v1/ocr")
def ocr(req: OcrReq) -> dict[str, Any]:
    path = _resolve_path(req.path)
    if req.path and path is None and not req.image_b64:
        raise HTTPException(404, "file not found")
    if not req.path and not req.image_b64:
        raise HTTPException(400, "path or image_b64 required")

    # PDF text layer — deterministic, no vision / paddle needed.
    if path and path.suffix.lower() == ".pdf":
        try:
            text = _pymupdf_text(path)
        except Exception:
            text = ""
        if len(text) >= MIN_TEXT:
            _flow("ocr", ok=True, path=str(path), chars=len(text), via="pymupdf")
            return {"ok": True, "text": text, "via": "pymupdf"}

    # --- Primary: PaddleOCR (images + scanned PDF pages) ---
    is_image = bool(
        req.image_b64
        or (path and path.suffix.lower() in IMAGE_EXTS)
    )
    is_scan_pdf = bool(path and path.suffix.lower() == ".pdf")

    if is_image or is_scan_pdf:
        _flow(
            "ocr_start",
            path=str(path or ""),
            mime="application/pdf" if is_scan_pdf else "image",
            via="paddle",
        )
        if is_scan_pdf and path is not None:
            paddle_text, paddle_err = _paddle_pdf_pages(path)
        else:
            paddle_text, paddle_err = _paddle_image(path, req.image_b64)
        if paddle_text and _text_usable(paddle_text):
            _flow(
                "ocr",
                ok=True,
                path=str(path or ""),
                chars=len(paddle_text),
                via="paddle",
            )
            return {"ok": True, "text": paddle_text, "via": "paddle"}
        if paddle_text and not _text_usable(paddle_text):
            _flow(
                "ocr",
                ok=False,
                path=str(path or ""),
                chars=len(paddle_text),
                error="paddle_noise",
                via="paddle",
            )
        elif paddle_err:
            _flow("ocr", ok=False, path=str(path or ""), error=paddle_err, via="paddle")

    # --- Vision combo (OCR_MODEL, default vision-ocr) after Paddle for images + scanned PDF ---
    status, body, text = 0, "", ""
    used = "paddle"
    if VISION and (is_image or is_scan_pdf) and _vision_ready():
        vision_inputs: list[tuple[str, str]] = []
        if is_scan_pdf and path is not None:
            for jpeg in _pymupdf_page_jpegs(path):
                vision_inputs.append((base64.b64encode(jpeg).decode("ascii"), "image/jpeg"))
        elif req.image_b64:
            vision_inputs.append((req.image_b64, "image/jpeg"))
        elif path is not None:
            raw = path.read_bytes()
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            vision_inputs.append((base64.b64encode(raw).decode("ascii"), mime))
        used = "vision-ocr"
        parts: list[str] = []
        for b64, mime in vision_inputs:
            _flow("ocr_start", path=str(path or ""), mime=mime, model=MODEL, via=used)
            status, body, chunk = _vision(b64, mime, req.prompt)
            refused = _llm_refused(status, body, chunk) or not chunk
            _vision_note(refused)
            if chunk and not _llm_refused(status, body, chunk):
                parts.append(chunk)
            if refused and not parts:
                break
        text = "\n\n".join(parts).strip()
        if text and len(text) >= MIN_TEXT:
            _flow("ocr", ok=True, path=str(path or ""), chars=len(text), via=used, model=MODEL)
            return {"ok": True, "text": text, "via": used}

    if not FALLBACK:
        _flow("ocr", ok=False, error="ocr_upstream_failed", path=str(path or ""))
        return {"ok": False, "error": "ocr_upstream_failed", "via": used}

    # --- Last: tesseract / pymupdf ---
    try:
        fb, via = _tesseract_local(path, req.image_b64)
    except Exception:
        fb, via = "", "none"
    if fb:
        _flow(
            "ocr",
            ok=True,
            path=str(path or ""),
            chars=len(fb),
            via=via,
            fallback=True,
        )
        return {"ok": True, "text": fb, "via": via, "fallback": True}

    _flow("ocr", ok=True, empty=True, path=str(path or ""), via=via or used)
    return _empty_ok(via or used)
