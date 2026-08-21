"""Pure helpers for Zalo inbound attachments (worker routing + recall memory).

Kept free of gateway imports so the rules stay unit-testable without Hermes.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple

TEXT_EXTS = (".txt", ".md", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml", ".xml")
OCR_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
OFFICE_EXTS = (".docx", ".xlsx", ".xlsm", ".xls", ".pptx")
AV_EXTS = (
    ".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi",
    ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac",
)

TEXT_CHARS = 20000
CONTEXT_CHARS = 8000
CONTEXT_ITEMS = 5
PROMPT_CHARS = 6000

# Hermes writes /opt/data/media/...; workers mount the same volume at /data/media.
_MEDIA_PREFIXES = ("/opt/data/media/", "/data/assistant/media/")
_WORKER_MEDIA_ROOT = "/data/media/"


def attachment_kind(file_name: str) -> str:
    """Which worker can read this file: text | ocr | office | av | none."""
    low = (file_name or "").lower()
    if low.endswith(TEXT_EXTS):
        return "text"
    if low.endswith(OCR_EXTS):
        return "ocr"
    if low.endswith(OFFICE_EXTS):
        return "office"
    if low.endswith(AV_EXTS):
        return "av"
    return "none"


def worker_media_path(local_path: str) -> str:
    """Rewrite a Hermes-local media path to the path workers see."""
    cont = str(local_path or "").replace("\\", "/")
    for prefix in _MEDIA_PREFIXES:
        if cont.startswith(prefix):
            return _WORKER_MEDIA_ROOT + cont[len(prefix) :]
    return cont


def stage_shared_media(
    local_path: str,
    file_name: str = "",
    *,
    thread_id: str = "",
    inbound_root: str = "/opt/data/media/inbound",
) -> str:
    """Copy a file into the shared media volume so OCR/ingest/dispatcher can read it.

    Hermes ``cache_image_from_bytes`` writes under ``/opt/data/replicas/.../cache/``,
    which workers do not mount. Without this copy, ``POST /v1/ocr`` returns 404 and
    the agent is asked to "open the image" with no vision tools — no Zalo reply.
    """
    import re
    import shutil
    import uuid
    from pathlib import Path

    src = Path(str(local_path or ""))
    if not src.is_file():
        return ""
    cont = str(src).replace("\\", "/")
    # Already on the shared volume — workers can see it after prefix rewrite.
    for prefix in _MEDIA_PREFIXES:
        if cont.startswith(prefix):
            return cont
    try:
        src.resolve().relative_to(Path(inbound_root).resolve())
        return cont
    except ValueError:
        pass
    safe = re.sub(r"[^\w.\-() ]", "_", (file_name or src.name))[:120].strip() or "file.bin"
    dest_dir = Path(inbound_root) / (str(thread_id or "dm").strip() or "dm")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex[:8]}_{safe}"
    shutil.copy2(src, dest)
    return str(dest)


def caption_payload(caption: Any) -> Dict[str, str]:
    """Zalo rejects document sends whose caption is blank, so omit it entirely."""
    text = str(caption or "")
    return {"caption": text} if text.strip() else {}


def context_decode(raw: Any) -> List[Dict[str, Any]]:
    """Remembered attachments, oldest first. Accepts the older single-item shape."""
    if not raw:
        return []
    try:
        data = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
    except (TypeError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict) and str(i.get("text") or "").strip()]
    if str(data.get("text") or "").strip():
        return [data]
    return []


def context_merge(
    items: List[Dict[str, Any]], file_name: str, text: str, *, now: float | None = None
) -> List[Dict[str, Any]]:
    """Append one file to the recall list, newest last, re-uploads replacing older entries."""
    name = str(file_name or "file")
    body = str(text or "")
    if not body.strip():
        return list(items or [])
    kept = [i for i in (items or []) if str(i.get("file") or "") != name]
    kept.append(
        {
            "file": name,
            "text": body[:CONTEXT_CHARS],
            "at": int(now if now is not None else time.time()),
        }
    )
    return kept[-CONTEXT_ITEMS:]


def context_encode(items: List[Dict[str, Any]]) -> str:
    return json.dumps({"items": list(items or [])}, ensure_ascii=False)


def context_blocks(items: List[Dict[str, Any]], *, budget: int = PROMPT_CHARS) -> List[str]:
    """Labelled text blocks for the prompt, newest first until the budget runs out."""
    blocks: List[str] = []
    left = max(0, int(budget))
    for item in reversed(items or []):
        if left <= 0:
            break
        body = str(item.get("text") or "")[:left]
        if not body:
            continue
        blocks.append(f"--- {item.get('file') or 'file'} ---\n{body}")
        left -= len(body)
    return blocks


def context_newest(items: List[Dict[str, Any]]) -> Tuple[str, str]:
    """(file_name, text) of the newest remembered attachment."""
    if not items:
        return "", ""
    last = items[-1]
    return str(last.get("file") or ""), str(last.get("text") or "")


def image_ocr_ack_message(excerpt: str, *, max_chars: int = 1800) -> str:
    """Deterministic Zalo reply for a bare image after OCR (empty or with text)."""
    body = ocr_excerpt_for_ack(excerpt)
    if not body:
        return (
            "Đã nhận ảnh. OCR không đọc được chữ rõ trong ảnh. "
            "Gửi ảnh có chữ nét hơn, hoặc nói rõ bạn muốn mình làm gì với ảnh này."
        )
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "…"
    return (
        "Đã đọc chữ trong ảnh (OCR):\n"
        f"{body}\n\n"
        "Bạn muốn mình tóm tắt / dịch / lưu knowledge không?"
    )


def file_extract_ack_message(
    file_name: str,
    excerpt: str,
    *,
    kind: str = "",
    max_chars: int = 1800,
) -> str:
    """Deterministic Zalo reply for a bare non-image attachment after extract."""
    name = (file_name or "file").strip() or "file"
    k = (kind or attachment_kind(name)).strip() or "none"
    if k == "ocr" and name.lower().endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
    ):
        return image_ocr_ack_message(excerpt, max_chars=max_chars)
    body = (excerpt or "").strip()
    if not body:
        if k == "av":
            return (
                f"Đã nhận media `{name}`. Chưa lấy được transcript / chữ trên khung hình. "
                "Gửi lại hoặc nói rõ bạn muốn mình làm gì tiếp."
            )
        return (
            f"Đã nhận file `{name}`. Chưa đọc được nội dung. "
            "Gửi lại hoặc đổi định dạng giúp mình."
        )
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "…"
    if k == "av":
        head = f"Đã đọc media `{name}` (transcript / chữ trên khung hình):"
    else:
        head = f"Đã đọc file `{name}`:"
    return (
        f"{head}\n{body}\n\n"
        "Bạn muốn mình tóm tắt / dịch / lưu knowledge không?"
    )


def ocr_excerpt_for_ack(excerpt: str) -> str:
    """Drop glyph-noise OCR (single-letter lines) so users get a clear empty ack."""
    body = (excerpt or "").strip()
    if not body:
        return ""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return ""
    if len(lines) >= 3:
        short = sum(1 for ln in lines if len(ln) <= 1)
        if short / len(lines) >= 0.6:
            return ""
    # Mostly punctuation / isolated chars with almost no words
    words = [w for w in body.replace("\n", " ").split() if len(w) >= 2]
    if len(body) >= 12 and len(words) <= 1 and len(lines) >= 4:
        return ""
    return body
