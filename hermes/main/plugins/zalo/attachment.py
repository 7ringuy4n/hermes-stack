"""Pure helpers for Zalo inbound attachments (worker routing + recall memory).

Kept free of gateway imports so the rules stay unit-testable without Hermes.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple

TEXT_EXTS = (".txt", ".md", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml", ".xml")
OCR_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
OFFICE_EXTS = (".docx", ".doc", ".xlsx", ".xlsm", ".xls", ".pptx")
AV_EXTS = (
    ".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi",
    ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac",
)
ARCHIVE_EXTS = (".zip", ".7z", ".rar", ".tar", ".tgz")


TEXT_CHARS = 20000
CONTEXT_CHARS = 12000
CONTEXT_ITEMS = 5
PROMPT_CHARS = 8000
# Keep workbook follow-ups usable for a full workday (not 15 minutes).
ATTACHMENT_CONTEXT_TTL_S_DEFAULT = 86400

# Hermes writes /opt/data/media/...; workers mount the same volume at /data/media.
_MEDIA_PREFIXES = ("/opt/data/media/", "/data/assistant/media/")
_WORKER_MEDIA_ROOT = "/data/media/"


def attachment_kind(file_name: str) -> str:
    """Which worker can read this file: text | ocr | office | av | archive | none."""
    low = (file_name or "").lower()
    if low.endswith(TEXT_EXTS):
        return "text"
    if low.endswith(OCR_EXTS):
        return "ocr"
    if low.endswith(OFFICE_EXTS):
        return "office"
    if low.endswith(AV_EXTS):
        return "av"
    if low.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        return "archive"
    if low.endswith(ARCHIVE_EXTS):
        return "archive"
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
    body = prefer_workbook_head(str(text or ""))
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


def prefer_workbook_head(text: str) -> str:
    """Keep sheet inventory + each ## Sheet header when truncating large workbooks."""
    raw = text or ""
    if "## Sheet" not in raw and "Workbook sheets:" not in raw:
        return raw
    lines = raw.splitlines()
    inv: list[str] = []
    bodies: list[tuple[str, list[str]]] = []
    cur_h = ""
    cur_b: list[str] = []
    in_inv = False
    for line in lines:
        if line.startswith("Workbook sheets:"):
            in_inv = True
            inv.append(line)
            continue
        if in_inv:
            if line.startswith("## Sheet"):
                in_inv = False
                # Fall through to sheet-header handling below.
            elif not line.strip():
                in_inv = False
                inv.append(line)
                continue
            else:
                inv.append(line)
                continue
        if line.startswith("## Sheet"):
            if cur_h:
                bodies.append((cur_h, cur_b))
            cur_h = line
            cur_b = []
            continue
        if cur_h:
            cur_b.append(line)
    if cur_h:
        bodies.append((cur_h, cur_b))
    if not bodies and not inv:
        return raw
    # Budget: inventory first; then each sheet header + a fair share of rows.
    head_parts = list(inv)
    if head_parts and head_parts[-1].strip():
        head_parts.append("")
    used = sum(len(x) + 1 for x in head_parts)
    left = max(0, CONTEXT_CHARS - used - 64)
    per = max(200, left // max(1, len(bodies))) if bodies else 0
    out = list(head_parts)
    for h, b in bodies:
        out.append(h)
        chunk = "\n".join(b)
        if len(chunk) > per:
            chunk = chunk[:per].rstrip() + "\n...(truncated)"
        if chunk:
            out.append(chunk)
    return "\n".join(out)[:CONTEXT_CHARS]


def split_workbook_sheets(extract: str) -> list[tuple[int, str, str]]:
    """Parse ingest markers into (1-based index, title, body)."""
    out: list[tuple[int, str, str]] = []
    cur_idx = 0
    cur_title = ""
    buf: list[str] = []
    for line in (extract or "").splitlines():
        if line.startswith("## Sheet"):
            if cur_idx > 0 or cur_title:
                out.append((cur_idx or len(out) + 1, cur_title, "\n".join(buf).strip()))
            rest = line[len("## Sheet") :].strip()
            # Formats: "2 (Name)" | ": Name" | "Name"
            idx = 0
            title = rest
            if rest.startswith(":"):
                title = rest[1:].strip()
            else:
                # "2 (Name)" or "2 Name"
                num = ""
                i = 0
                while i < len(rest) and rest[i].isdigit():
                    num += rest[i]
                    i += 1
                if num:
                    idx = int(num)
                    rem = rest[i:].strip()
                    if rem.startswith("(") and rem.endswith(")"):
                        title = rem[1:-1].strip()
                    elif rem.startswith("(") and ")" in rem:
                        title = rem[1 : rem.index(")")].strip()
                    else:
                        title = rem or num
                else:
                    title = rest
            cur_idx = idx or (len(out) + 1)
            cur_title = title or f"Sheet {cur_idx}"
            buf = []
            continue
        if cur_idx or cur_title:
            buf.append(line)
    if cur_idx or cur_title:
        out.append((cur_idx or len(out) + 1, cur_title, "\n".join(buf).strip()))
    return out


def sheet_ref_from_text(blob: str) -> str:
    """Pull SHEET_REF: value from classify-authored contract text (not user NLU)."""
    for raw in (blob or "").splitlines():
        line = raw.strip()
        if line.upper().startswith("SHEET_REF:"):
            return line.split(":", 1)[1].strip()
    # Also allow inline mid-line marker
    up = (blob or "").upper()
    key = "SHEET_REF:"
    j = up.find(key)
    if j >= 0:
        val = (blob or "")[j + len(key) :].splitlines()[0].strip()
        return val
    return ""


def pick_sheet_section(extract: str, sheet_ref: str) -> tuple[str, str]:
    """Return (title, body) for SHEET_REF index or title. Empty if not found."""
    sheets = split_workbook_sheets(extract)
    if not sheets:
        return "", ""
    ref = (sheet_ref or "").strip()
    if not ref:
        return "", ""
    if ref.isdigit():
        want = int(ref)
        for idx, title, body in sheets:
            if idx == want:
                return title, body
        if 1 <= want <= len(sheets):
            _i, title, body = sheets[want - 1]
            return title, body
        return "", ""
    ref_l = ref.lower()
    for idx, title, body in sheets:
        if title.lower() == ref_l or title.lower().startswith(ref_l):
            return title, body
    return "", ""


def workbook_sheet_reply(
    file_name: str, extract: str, sheet_ref: str, *, max_chars: int = 1800
) -> str:
    """User-facing reply describing one sheet from remembered extract."""
    name = (file_name or "workbook").strip() or "workbook"
    title, body = pick_sheet_section(extract, sheet_ref)
    sheets = split_workbook_sheets(extract)
    if not sheets:
        return ""
    if not title:
        inv = ", ".join(f"{i}={t}" for i, t, _ in sheets[:12])
        return (
            f"File `{name}` có {len(sheets)} sheet: {inv}. "
            "Nói rõ sheet số mấy (hoặc tên sheet) bạn muốn mình mô tả."
        )
    preview = (body or "").strip()
    if len(preview) > max_chars:
        preview = preview[:max_chars].rstrip() + "…"
    if not preview:
        preview = "(sheet trống — không có nội dung chữ)"
    return f"Sheet {sheet_ref} trong file {name} — {title}:\n{preview}"


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


# Zalo sometimes sends numeric cliMsgType (e.g. 32 = photo) instead of chat.photo.
ZALO_MSG_TYPE_NUM_MAP: Dict[str, str] = {
    "1": "webchat",
    "32": "chat.photo",
    "31": "chat.voice",
    "44": "chat.video.msg",
    "46": "share.file",
    "49": "chat.gif",
}


def normalize_zalo_msg_type(msg_type: Any) -> str:
    mt = str(msg_type or "").strip()
    return ZALO_MSG_TYPE_NUM_MAP.get(mt, mt)


def quote_content_blob(quote: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort content object for a quoted message (content + attach + propertyExt).

    Inbound Zalo TQuote uses ``attach`` (JSON string) + ``cliMsgType`` + ``msg``,
    not ``content``/``msgType`` like a normal TMessage.
    """
    if not isinstance(quote, dict):
        return {}
    blob: Dict[str, Any] = {}
    attach = quote.get("attach")
    if isinstance(attach, str) and attach.strip():
        try:
            attach = json.loads(attach)
        except Exception:
            attach = None
    if isinstance(attach, dict):
        blob.update(attach)
    qc = quote.get("content")
    if qc is None:
        qc = quote.get("msg") if quote.get("msg") is not None else quote.get("text")
    if isinstance(qc, str) and qc.strip():
        if not blob.get("title"):
            blob["title"] = qc.strip()
    elif isinstance(qc, dict):
        blob = {**blob, **qc}
    pe = quote.get("propertyExt") or quote.get("propExt")
    if isinstance(pe, str):
        try:
            pe = json.loads(pe)
        except Exception:
            pe = None
    if isinstance(pe, dict):
        for key in (
            "href",
            "thumb",
            "hd",
            "hdUrl",
            "thumbUrl",
            "normalUrl",
            "oriUrl",
            "rawUrl",
            "title",
            "description",
            "params",
            "width",
            "height",
        ):
            if key not in blob and pe.get(key) is not None:
                blob[key] = pe[key]
    return blob


def _quote_href_from_blob(qc: Dict[str, Any], params: Dict[str, Any]) -> str:
    """Pick a downloadable URL from quote content/attach/params."""
    for key in (
        "href",
        "fileUrl",
        "downloadUrl",
        "normalUrl",
        "hd",
        "hdUrl",
        "oriUrl",
        "rawUrl",
        "url",
        "thumb",
        "thumbUrl",
    ):
        val = str(qc.get(key) or "").strip()
        if val.startswith("http"):
            return val
    for key in (
        "fileUrl",
        "downloadUrl",
        "hd",
        "hdUrl",
        "normal",
        "normalUrl",
        "oriUrl",
        "rawUrl",
        "m4a",
        "href",
        "url",
        "thumb",
    ):
        val = str(params.get(key) or "").strip()
        if val.startswith("http"):
            return val
    return ""


def quote_is_media_type(msg_type: Any) -> bool:
    mt = normalize_zalo_msg_type(msg_type).lower()
    return any(tok in mt for tok in ("photo", "gif", "image", "voice", "video", "file", "share."))


def extract_media_from_quote(quote: Any) -> Dict[str, Any] | None:
    """Build inbound media dict from a quoted Zalo message (quote-reply to photo/file)."""
    if not isinstance(quote, dict):
        return None
    # Prefer pre-built media from bridge when present.
    pre = quote.get("media")
    if isinstance(pre, dict) and str(pre.get("url") or "").startswith("http"):
        return dict(pre)
    qtype = normalize_zalo_msg_type(quote.get("msgType") or quote.get("cliMsgType") or "")
    qc = quote_content_blob(quote)
    params = qc.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            params = {}
    if not isinstance(params, dict):
        params = {}
    href = _quote_href_from_blob(qc, params)
    media_hint = bool(href) or quote_is_media_type(qtype)
    if not media_hint or not href:
        return None
    mt_low = qtype.lower()
    if "photo" in mt_low or "gif" in mt_low or "image" in mt_low:
        kind = "image"
    elif "voice" in mt_low or "audio" in mt_low:
        kind = "voice"
    elif "video" in mt_low:
        kind = "video"
    else:
        kind = "file"
    title = str(
        qc.get("title")
        or params.get("fileName")
        or params.get("title")
        or quote.get("fileName")
        or ""
    ).strip()
    ext_raw = params.get("fileExt") if isinstance(params, dict) else None
    ext = str(ext_raw or "").strip().lstrip(".")
    if not ext and "." in title:
        ext = title.rsplit(".", 1)[-1].strip()
    if not ext:
        ext = "bin"
    if kind == "image" and (not ext or ext == "bin" or len(str(ext)) > 5):
        ext = "jpg"
    file_name = title if title else f"file.{ext}"
    # Ensure archive/office extensions survive when Zalo only sends fileExt.
    if "." not in file_name and ext and ext != "bin":
        file_name = f"{file_name}.{ext}"
    return {
        "kind": kind,
        "url": href,
        "fileName": file_name,
        "ext": ext,
        "mime": "image/jpeg"
        if kind == "image"
        else ("audio/aac" if kind == "voice" else "application/octet-stream"),
        "size": (params.get("fileSize") if isinstance(params, dict) else 0) or 0,
    }


def quoted_context_snip(quote: Any, *, max_chars: int = 2000) -> str:
    """Plain text / file title from a Zalo quote payload for the agent prompt.

    Works for DM and group quote-replies. Prefer real body text; for media quotes
    without captions still return a typed placeholder so Hermes can act.
    """
    if not isinstance(quote, dict):
        return ""
    qtype = normalize_zalo_msg_type(quote.get("msgType") or quote.get("cliMsgType") or "")
    qc_raw = quote.get("content")
    if qc_raw is None:
        qc_raw = quote.get("msg") if quote.get("msg") is not None else quote.get("text")
    if isinstance(qc_raw, str) and qc_raw.strip():
        body = qc_raw.strip()
    else:
        qc = quote_content_blob(quote)
        title = str(qc.get("title") or "").strip()
        desc = str(qc.get("description") or "").strip()
        href = str(qc.get("href") or qc.get("thumb") or "").strip()
        params = qc.get("params") or {}
        if isinstance(params, str):
            try:
                import json as _json

                params = _json.loads(params)
            except Exception:
                params = {}
        if not isinstance(params, dict):
            params = {}
        file_name = str(
            params.get("fileName")
            or params.get("title")
            or qc.get("fileName")
            or title
            or ""
        ).strip()
        parts = [p for p in (title, desc, file_name) if p]
        # Dedupe while preserving order
        seen = set()
        parts = [p for p in parts if not (p in seen or seen.add(p))]
        body = "\n".join(parts) if parts else (href[:180] if href else "")
        if not body:
            low = qtype.lower()
            if "photo" in low or "gif" in low or "image" in low:
                body = "[quoted image]"
            elif "voice" in low or "audio" in low:
                body = "[quoted voice]"
            elif "video" in low:
                body = "[quoted video]"
            elif "file" in low or "share" in low:
                body = f"[quoted file{(': ' + file_name) if file_name else ''}]"
        if not body:
            body = str(quote.get("msg") or quote.get("text") or quote.get("body") or "").strip()
    if not body and qtype:
        body = f"[quoted message type={qtype}]"
    if not body:
        return ""
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "…"
    return body


def song_hint_from_filename(file_name: str) -> str:
    """Best-effort song/artist hint from an audio/video filename."""
    name = (file_name or "").strip()
    if not name:
        return ""
    low = name.lower()
    stem = name.rsplit(".", 1)[0] if "." in name else name
    for noise in (
        "official lyric video",
        "official music video",
        "lyric video",
        "official audio",
        "audio",
        "lyrics",
        "mv",
    ):
        # case-insensitive remove
        idx = stem.lower().find(noise)
        if idx >= 0:
            stem = (stem[:idx] + stem[idx + len(noise) :]).strip(" -_[](){}")
    stem = " ".join(stem.replace("_", " ").replace("  ", " ").split())
    if not stem:
        return name
    if low.endswith(AV_EXTS):
        return stem
    return ""


def image_analyze_ack_message(excerpt: str, *, max_chars: int = 1800) -> str:
    """Zalo reply after OCR and/or vision-ocr analyze. Empty excerpt → caller falls through."""
    raw = (excerpt or "").strip()
    if not raw:
        return ""
    ocr_body = ocr_excerpt_for_ack(excerpt)
    if ocr_body:
        body = ocr_body
        ocr_mode = True
    elif len(raw) >= 12 and len([w for w in raw.split() if len(w) >= 2]) >= 3:
        body = raw
        ocr_mode = False
    else:
        return ""
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "…"
    if ocr_mode:
        return (
            "Đã phân tích ảnh:\n"
            f"{body}\n\n"
            "Bạn muốn mình tóm tắt / dịch / lưu knowledge không?"
        )
    return (
        "Đã phân tích ảnh:\n"
        f"{body}\n\n"
        "Bạn muốn mình tóm tắt / dịch / lưu knowledge không?"
    )


def image_ocr_ack_message(excerpt: str, *, max_chars: int = 1800) -> str:
    """Legacy name — prefer image_analyze_ack_message (falls through when empty)."""
    ack = image_analyze_ack_message(excerpt, max_chars=max_chars)
    if ack:
        return ack
    return (
        "Đã nhận ảnh. OCR không đọc được chữ rõ trong ảnh. "
        "Gửi ảnh có chữ nét hơn, hoặc nói rõ bạn muốn mình làm gì với ảnh này."
    )


def archive_password_ack_message(file_name: str, *, bad: bool = False) -> str:
    """Ask the user for an archive password — never attempt brute force."""
    name = (file_name or "archive").strip() or "archive"
    if bad:
        return (
            f"Mật khẩu không đúng cho archive `{name}`. "
            "Gửi lại file kèm mật khẩu đúng trong caption (ví dụ: `password: ...`)."
        )
    return (
        f"Archive `{name}` đang được bảo vệ bằng mật khẩu. "
        "Gửi lại kèm mật khẩu trong caption (ví dụ: `password: ...`). "
        "Chỉ giải nén file media bên trong — không mở file khác."
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
    # Whitespace-only office extracts are blank docs (ingest worker), not read failures.
    compact = "".join((excerpt or "").split())
    body = (excerpt or "").strip() if compact else ""
    if not body:
        if k == "av":
            return (
                f"Đã nhận media `{name}`. Chưa lấy được transcript / chữ trên khung hình. "
                "Gửi lại hoặc nói rõ bạn muốn mình làm gì tiếp."
            )
        if k == "office":
            return (
                f"Đã nhận file `{name}`. File trống — không có nội dung chữ để trích xuất. "
                "Gửi file có nội dung hoặc nói rõ bạn muốn mình làm gì tiếp."
            )
        if k == "archive":
            return (
                f"Đã nhận archive `{name}`. Không có media (ảnh/pdf/office/text/av) bên trong "
                "để đọc — chỉ xử lý file media, bỏ qua file khác và archive lồng nhau."
            )
        return (
            f"Đã nhận file `{name}`. Chưa đọc được nội dung. "
            "Gửi lại hoặc đổi định dạng giúp mình."
        )
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "…"
    if k == "av":
        head = f"Đã đọc media `{name}` (transcript / chữ trên khung hình):"
    elif k == "archive":
        head = f"Đã giải nén `{name}` (chỉ media):"
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
