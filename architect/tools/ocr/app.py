"""OCR — 9Router vision first; local pymupdf / tesseract if the LLM refuses."""
from __future__ import annotations

import base64
import io
import os
import re
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

API_KEY = (
    os.environ.get("OPENAI_API_KEY")
    or os.environ.get("N9ROUTER_API_KEY")
    or os.environ.get("OCR_API_KEY")
    or ""
).strip()
BASE = os.environ.get("OPENAI_BASE_URL", "http://9router:20128/v1").rstrip("/")
MODEL = os.environ.get("OCR_MODEL") or os.environ.get("OPENAI_MODEL") or "hermes"
MEDIA_ROOT = Path(os.environ.get("OCR_MEDIA_ROOT", "/data/media"))
FALLBACK = (os.environ.get("OCR_FALLBACK") or "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
MIN_TEXT = int(os.environ.get("OCR_MIN_CHARS", "24"))

_REFUSE_RE = re.compile(
    r"can't|cannot|unable to|don't support|do not support|not (?:able|supported)|"
    r"no vision|image not|refuse|i'm just a language|text-only|"
    r"model_not_found|was retired|request too large|oneOf at",
    re.I,
)

app = FastAPI(title="assistant-ocr", version="1.2.0")


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


class OcrReq(BaseModel):
    path: Optional[str] = None
    image_b64: Optional[str] = None
    prompt: str = Field(default="Extract all text as markdown. Preserve tables if present.")


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
        "model": MODEL,
        "via": "9router",
        "configured": bool(API_KEY and BASE),
        "fallback": FALLBACK,
        "tesseract": tess,
    }


def _resolve_path(raw: Optional[str]) -> Optional[Path]:
    if not raw:
        return None
    s = str(raw).strip()
    # Hermes writes under /opt/data/media; OCR mounts the same volume at /data/media.
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


def _llm_refused(status: int, body: str, text: str) -> bool:
    if status in {400, 404, 410, 413, 415, 422, 429, 500, 502, 503}:
        return True
    blob = f"{body}\n{text}"
    if _REFUSE_RE.search(blob):
        return True
    return False


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


def _vision(b64: str, mime: str, prompt: str) -> tuple[int, str, str]:
    """Return (status, raw_body, extracted_text). status 0 = transport error."""
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


def _fallback_local(path: Optional[Path], image_b64: Optional[str]) -> tuple[str, str]:
    """(text, via) — pymupdf text layer, then tesseract on image/PDF renders."""
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


@app.post("/v1/ocr")
def ocr(req: OcrReq) -> dict[str, Any]:
    path = _resolve_path(req.path)
    if req.path and path is None and not req.image_b64:
        raise HTTPException(404, "file not found")

    # PDF with a text layer: skip vision (avoids 413 / text-only model refuse).
    if path and path.suffix.lower() == ".pdf":
        try:
            text = _pymupdf_text(path)
        except Exception:
            text = ""
        if len(text) >= MIN_TEXT:
            _flow("ocr", ok=True, path=str(path), chars=len(text), via="pymupdf")
            return {"ok": True, "text": text, "via": "pymupdf"}

    status, body, text = 0, "", ""
    used = "none"
    if path and path.suffix.lower() == ".pdf":
        try:
            jpegs = _pymupdf_page_jpegs(path)
        except Exception:
            jpegs = []
        pages: list[str] = []
        refused = False
        for jpeg in jpegs:
            b64 = base64.b64encode(jpeg).decode("ascii")
            st, bd, tx = _vision(b64, "image/jpeg", req.prompt)
            status, body = st, bd
            if _llm_refused(st, bd, tx) or not tx:
                refused = True
                break
            pages.append(tx)
        if pages and not refused:
            text = "\n\n".join(pages)
            used = "9router"
        else:
            text = ""
            used = "9router"
    elif req.image_b64 or (path and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}):
        if req.image_b64:
            b64, mime = req.image_b64, "image/jpeg"
        else:
            raw = path.read_bytes()  # type: ignore[union-attr]
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"  # type: ignore[union-attr]
            b64 = base64.b64encode(raw).decode("ascii")
        _flow("ocr_start", path=str(path or ""), mime=mime, model=MODEL, via="9router")
        status, body, text = _vision(b64, mime, req.prompt)
        used = "9router"
    else:
        # unknown type — try pymupdf then vision skip
        status, body, text = 0, "unsupported", ""

    if text and len(text) >= MIN_TEXT and not _llm_refused(status, body, text):
        _flow("ocr", ok=True, path=str(path or ""), chars=len(text), via=used, model=MODEL)
        return {"ok": True, "text": text, "via": used}

    if not FALLBACK:
        _flow("ocr", ok=False, error="ocr_upstream_failed", path=str(path or ""))
        return {"ok": False, "error": "ocr_upstream_failed", "via": used}

    try:
        fb, via = _fallback_local(path, req.image_b64)
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

    _flow("ocr", ok=False, error="ocr_failed", path=str(path or ""), via=used)
    return {"ok": False, "error": "ocr_failed", "via": used}
