"""Office file create + Zalo send. Enable: OFFICE_FILE_GEN=active (compose / Media worker).

PDF path: LLM authors HTML (preferred) or raw PDF bytes; dispatcher converts HTML→PDF.
No ReportLab layout templates.
"""
from __future__ import annotations

import base64
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("office_file")

_OFFICE_OK = {".txt", ".csv", ".md", ".xlsx", ".docx", ".pdf", ".pptx"}
_KIND_EXT = {
    "pdf": ".pdf",
    "txt": ".txt",
    "text": ".txt",
    "docx": ".docx",
    "xlsx": ".xlsx",
    "csv": ".csv",
    "md": ".md",
    "markdown": ".md",
    "pptx": ".pptx",
    "ppt": ".pptx",
}

_MEDIA_ROOTS = (
    Path("/opt/data/media/out"),
    Path("/data/assistant/media/out"),
    Path("/opt/data/media/inbound"),
    Path("/data/assistant/media/inbound"),
)

try:
    from pydantic import BaseModel as _PydanticBase
except ImportError:  # unit hosts without pydantic
    class _PydanticBase:  # type: ignore[no-redef]
        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)


class OfficeFileReq(_PydanticBase):
    prompt: str = ""
    thread_id: str = ""
    thread_type: str = "user"
    caption: str = ""
    filename: Optional[str] = None
    output_type: Optional[str] = None


def _enabled() -> bool:
    v = (
        os.environ.get("OFFICE_FILE_GEN") or os.environ.get("ZALO_OFFICE_FILE") or "inactive"
    ).strip().lower()
    return v in {"1", "true", "yes", "on", "active"}


def is_compound_office_request(text: str) -> bool:
    """Compounds are classify's job. Host never scans kinds in user prose."""
    del text
    return False


def parse_office(prompt: str, output_type: str = "") -> tuple[str, str]:
    """Return (ext, body) from classify inner work + output_type. No prose NLU."""
    body = (prompt or "").strip() or " "
    kind = (output_type or "").strip().lower().lstrip(".")
    ext = _KIND_EXT.get(kind, ".txt")
    return ext, body


def parse_office_jobs(prompt: str, output_type: str = "") -> list[tuple[str, str]]:
    """One office prompt → one job. Classify already split compounds."""
    raw = (prompt or "").strip()
    if not raw:
        return []
    return [parse_office(raw, output_type)]


def _skip_structural_junk(line: str) -> bool:
    """Drop empty lines, URLs, JSON blobs, unfilled templates, markdown table chrome."""
    s = (line or "").strip()
    if not s or len(s) < 2:
        return True
    if s.startswith(("{", "[", "'{", '"{')):
        return True
    if "{'" in s or '{"' in s:
        return True
    low = s.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return True
    if "value after" in low or "<value" in low:
        return True
    if "safe-for-work" in low or "safe for work" in low:
        return True
    if s.startswith("|"):
        core = (
            s.replace("|", "")
            .replace("-", "")
            .replace(":", "")
            .replace(" ", "")
            .replace(".", "")
        )
        if not core:
            return True
    return False


def _looks_like_pdf_bytes(data: bytes) -> bool:
    return bool(data) and data.lstrip().startswith(b"%PDF")


def _decode_pdf_body(body: str) -> bytes | None:
    """Accept raw %PDF text or PDF_BASE64: / data:application/pdf;base64, payloads."""
    raw = (body or "").strip()
    if not raw:
        return None
    if raw.lstrip().startswith("%PDF"):
        return raw.encode("latin-1", errors="ignore")
    marker = "PDF_BASE64:"
    if raw.upper().startswith(marker):
        b64 = raw[len(marker) :].strip()
        try:
            blob = base64.b64decode(b64, validate=False)
        except Exception:  # noqa: BLE001
            return None
        return blob if _looks_like_pdf_bytes(blob) else None
    prefix = "data:application/pdf;base64,"
    if raw.lower().startswith(prefix):
        try:
            blob = base64.b64decode(raw[len(prefix) :].strip(), validate=False)
        except Exception:  # noqa: BLE001
            return None
        return blob if _looks_like_pdf_bytes(blob) else None
    return None


def _unwrap_fenced(body: str, *, lang: str) -> str | None:
    """Pull content from ```lang ... ``` fences without regex."""
    s = (body or "").strip()
    if not s.startswith("```"):
        return None
    first_nl = s.find("\n")
    if first_nl < 0:
        return None
    header = s[3:first_nl].strip().lower()
    if header and header != lang.lower():
        return None
    rest = s[first_nl + 1 :]
    end = rest.rfind("```")
    if end < 0:
        return None
    return rest[:end].strip() or None


def _extract_html(body: str) -> str | None:
    """Return HTML document/fragment authored by the LLM, if present."""
    s = (body or "").strip()
    if not s:
        return None
    fenced = _unwrap_fenced(s, lang="html")
    if fenced:
        s = fenced
    low = s.lower().lstrip()
    if low.startswith("<!doctype") or low.startswith("<html"):
        return s
    if "<html" in low:
        idx = low.find("<html")
        return s[idx:]
    # HTML fragment (has tags) — wrap later
    if "<" in s and "</" in s and ("<div" in low or "<p" in low or "<h1" in low or "<table" in low or "<section" in low or "<img" in low):
        return s
    return None


def _resolve_media_path(raw: str) -> Path | None:
    p = (raw or "").strip().strip("'").strip('"')
    if p.startswith("file://"):
        p = p[7:]
    if not p:
        return None
    candidates: list[Path] = []
    if p.startswith("/"):
        candidates.append(Path(p))
    for base in _MEDIA_ROOTS:
        candidates.append(base / p)
        if p.startswith("media/"):
            candidates.append(base.parent / p)
    for cand in candidates:
        try:
            if cand.is_file():
                return cand
        except OSError:
            continue
    return None


def _html_document(fragment_or_doc: str) -> str:
    """Ensure a full HTML document with Unicode-friendly base CSS."""
    src = (fragment_or_doc or "").strip()
    low = src.lower().lstrip()
    if low.startswith("<!doctype") or low.startswith("<html"):
        return src
    return (
        "<!DOCTYPE html>\n"
        '<html lang="vi"><head><meta charset="utf-8"/>'
        "<title>Document</title>"
        "<style>"
        "html,body{margin:0;padding:0;font-family:'Noto Sans',DejaVu Sans,Arial,sans-serif;"
        "color:#142033;background:#f4f7fb;}"
        "main{padding:28px 32px;}"
        "h1{font-size:28px;margin:0 0 8px;color:#1a3a66;}"
        "h2{font-size:16px;margin:0 0 18px;color:#5a6a7a;font-weight:600;}"
        ".hero{width:100%;max-height:280px;object-fit:cover;border-radius:12px;margin:0 0 18px;}"
        ".cards{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0 20px;}"
        ".card{background:#fff;border:1px solid #d9e6f5;border-radius:12px;padding:12px 14px;}"
        ".card .k{font-size:11px;color:#2a6ebd;text-transform:uppercase;letter-spacing:.02em;}"
        ".card .v{font-size:16px;margin-top:4px;}"
        "ul{padding-left:18px;} li{margin:4px 0;} p{line-height:1.45;}"
        "</style></head><body><main>"
        f"{src}"
        "</main></body></html>"
    )


def _rewrite_img_src_to_file_urls(html: str) -> str:
    """Turn hermes media paths in src= into file:// URLs WeasyPrint can open."""
    out: list[str] = []
    i = 0
    src_token = 'src="'
    src_token2 = "src='"
    while i < len(html):
        lower = html.lower()
        a = lower.find(src_token, i)
        b = lower.find(src_token2, i)
        if a < 0 and b < 0:
            out.append(html[i:])
            break
        if a < 0 or (b >= 0 and b < a):
            quote = "'"
            start = b
            token = src_token2
        else:
            quote = '"'
            start = a
            token = src_token
        out.append(html[i:start + len(token)])
        end = html.find(quote, start + len(token))
        if end < 0:
            out.append(html[start + len(token) :])
            break
        raw_src = html[start + len(token) : end]
        path = _resolve_media_path(raw_src)
        if path is not None:
            out.append(path.resolve().as_uri())
        else:
            out.append(raw_src)
        out.append(quote)
        i = end + 1
    return "".join(out)


def write_pdf_from_html(dest: Path, html: str) -> Path:
    """Convert LLM HTML to PDF (WeasyPrint when available; else PyMuPDF Story)."""
    import contextlib
    import io

    doc = _rewrite_img_src_to_file_urls(_html_document(html))
    base = str(_MEDIA_ROOTS[0]) if _MEDIA_ROOTS[0].is_dir() else str(dest.parent)
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            from weasyprint import HTML

            HTML(string=doc, base_url=base).write_pdf(str(dest))
        return dest
    except Exception as e:  # noqa: BLE001
        log.warning("weasyprint html->pdf skipped: %s", type(e).__name__)
    return _write_pdf_pymupdf_story(dest, doc)


def _write_pdf_pymupdf_story(dest: Path, html: str) -> Path:
    """HTML→PDF via PyMuPDF Story (no GTK; good Unicode coverage)."""
    import pymupdf

    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (36, 36, -36, -36)
    story = pymupdf.Story(html=html)
    writer = pymupdf.DocumentWriter(str(dest))
    more = True
    while more:
        device = writer.begin_page(mediabox)
        more, where = story.place(where)
        story.draw(device)
        writer.end_page()
        where = mediabox + (36, 36, -36, -36)
    writer.close()
    return dest


def write_pdf(dest: Path, body: str) -> Path:
    """Write PDF from LLM HTML or raw/base64 PDF. No ReportLab page layout."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    pdf_blob = _decode_pdf_body(body)
    if pdf_blob is not None:
        dest.write_bytes(pdf_blob)
        return dest
    html = _extract_html(body)
    if html:
        return write_pdf_from_html(dest, html)
    # Last resort: wrap plain text as a minimal HTML page (not a card template).
    safe = (
        (body or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    paragraphs = []
    for line in safe.splitlines() or [safe]:
        if not line.strip():
            continue
        paragraphs.append(f"<p>{line}</p>")
    return write_pdf_from_html(dest, "\n".join(paragraphs) or "<p> </p>")


def write_pptx_styled(dest: Path, body: str) -> Path:
    """Markdown-ish body → title + facts/sections PPTX deck."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    title = ""
    subtitle = ""
    facts: list[str] = []
    prose: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    cur_section = ""
    cur_bullets: list[str] = []

    def flush_section() -> None:
        nonlocal cur_section, cur_bullets
        if cur_section or cur_bullets:
            sections.append((cur_section or "Chi tiết", list(cur_bullets)))
        cur_section = ""
        cur_bullets = []

    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("image:"):
            continue
        if line.startswith("#"):
            hashes = 0
            while hashes < len(line) and line[hashes] == "#":
                hashes += 1
            rest = line[hashes:].strip()
            if hashes == 1 and rest and not title:
                title = rest[:80]
                continue
            if hashes == 2 and rest and not subtitle and not sections and not facts:
                subtitle = rest[:100]
                continue
            if rest:
                flush_section()
                cur_section = rest[:80]
            continue
        if line.startswith(("- ", "• ", "* ")):
            item = line[2:].strip()
            if item and not _skip_structural_junk(item):
                if cur_section:
                    cur_bullets.append(item)
                else:
                    facts.append(item)
            continue
        if _skip_structural_junk(line):
            continue
        prose.append(line)

    flush_section()
    if not title:
        title = (prose.pop(0) if prose else "Báo cáo")[:72]

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    def _fill_para(para, text: str, *, size: int, bold: bool = False, color=(16, 32, 56)) -> None:
        para.text = text
        for run in para.runs:
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = RGBColor(*color)
            run.font.name = "Calibri"

    def _add_bullets(slide, heading: str, items: list[str]) -> None:
        h = slide.shapes.add_textbox(Inches(0.7), Inches(0.4), Inches(12), Inches(0.7))
        _fill_para(h.text_frame.paragraphs[0], heading[:60], size=24, bold=True)
        body_box = slide.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(12), Inches(5.5))
        btf = body_box.text_frame
        btf.word_wrap = True
        first = True
        for item in items[:12]:
            para = btf.paragraphs[0] if first else btf.add_paragraph()
            first = False
            _fill_para(para, f"• {item[:120]}", size=18)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(0.7), Inches(2.2), Inches(12), Inches(1.2))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    _fill_para(p, title, size=36, bold=True)
    if subtitle:
        sub = slide.shapes.add_textbox(Inches(0.7), Inches(3.5), Inches(12), Inches(0.8))
        _fill_para(
            sub.text_frame.paragraphs[0],
            subtitle,
            size=18,
            bold=False,
            color=(70, 90, 110),
        )

    if facts:
        _add_bullets(prs.slides.add_slide(prs.slide_layouts[6]), title[:60], facts)

    for sec_title, bullets in sections[:6]:
        rows = bullets or prose[:6]
        if rows:
            _add_bullets(prs.slides.add_slide(prs.slide_layouts[6]), sec_title[:60], rows)

    if prose and not sections and not facts:
        _add_bullets(prs.slides.add_slide(prs.slide_layouts[6]), title[:60], prose[:10])

    prs.save(str(dest))
    return dest


def write_office(dest: Path, ext: str, body: str) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if ext in {".txt", ".md", ".csv"}:
        data = body if body.endswith("\n") else body + "\n"
        dest.write_text(data, encoding="utf-8")
        return dest
    if ext == ".xlsx":
        try:
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            for i, line in enumerate((body.splitlines() or [body]), start=1):
                ws.cell(row=i, column=1, value=line)
            wb.save(dest)
            return dest
        except Exception as e:  # noqa: BLE001
            log.warning("xlsx write failed, fallback csv: %s", e)
            dest = dest.with_suffix(".csv")
            dest.write_text(body + "\n", encoding="utf-8")
            return dest
    if ext == ".docx":
        try:
            from docx import Document

            doc = Document()
            for line in body.splitlines() or [body]:
                doc.add_paragraph(line)
            doc.save(dest)
            return dest
        except Exception as e:  # noqa: BLE001
            log.warning("docx write failed, fallback txt: %s", e)
            dest = dest.with_suffix(".txt")
            dest.write_text(body + "\n", encoding="utf-8")
            return dest
    if ext == ".pdf":
        try:
            return write_pdf(dest, body)
        except Exception as e:  # noqa: BLE001
            log.warning("pdf write failed, fallback txt: %s", type(e).__name__)
            dest = dest.with_suffix(".txt")
            dest.write_text(body + "\n", encoding="utf-8")
            return dest
    if ext == ".pptx":
        try:
            return write_pptx_styled(dest, body)
        except Exception as e:  # noqa: BLE001
            log.warning("pptx write failed, fallback pdf: %s", type(e).__name__)
            dest = dest.with_suffix(".pdf")
            try:
                return write_pdf(dest, body)
            except Exception as e2:  # noqa: BLE001
                log.warning("pptx→pdf fallback failed: %s", type(e2).__name__)
                dest = dest.with_suffix(".txt")
                dest.write_text(body + "\n", encoding="utf-8")
                return dest
    dest.write_text(body + "\n", encoding="utf-8")
    return dest


def register_office_file(
    app: Any,
    media_dir: Path,
    deliver: Callable[..., dict[str, Any]],
) -> None:
    from fastapi import HTTPException

    @app.post("/v1/office-file")
    def office_file(req: OfficeFileReq) -> dict[str, Any]:
        if not _enabled():
            raise HTTPException(
                503,
                os.environ.get(
                    "OFFICE_DISABLED_MESSAGE",
                    "Office file generation is unavailable.",
                ),
            )
        prompt = (req.prompt or "").strip()
        if not prompt:
            raise HTTPException(400, "prompt required")
        if not req.thread_id:
            raise HTTPException(400, "thread_id required")

        jobs = parse_office_jobs(prompt, req.output_type or "")
        if not jobs:
            raise HTTPException(400, "prompt required")
        for ext, _body in jobs:
            if ext not in _OFFICE_OK:
                raise HTTPException(400, f"unsupported {ext}")

        caption = (req.caption if req.caption is not None else "").strip()
        base_name = (req.filename or "").strip()
        files: list[dict[str, Any]] = []
        zalo: Any = None
        zalo_error: Any = None

        for i, (ext, body) in enumerate(jobs):
            if base_name and len(jobs) == 1:
                name = base_name
            elif base_name and len(jobs) > 1:
                name = f"{Path(base_name).stem}-{i + 1}{ext}"
            else:
                name = f"file-{uuid.uuid4().hex[:8]}{ext}"
            if Path(name).suffix.lower() != ext:
                name = f"{Path(name).stem}{ext}"
            dest = media_dir / "out" / name
            dest = write_office(dest, ext, body)
            try:
                zalo = deliver(
                    path=str(dest),
                    thread_id=req.thread_id,
                    thread_type=req.thread_type or "user",
                    caption=caption,
                    filename=dest.name,
                    lock_thread=True,
                )
            except Exception as e:  # noqa: BLE001
                zalo_error = str(getattr(e, "detail", None) or e)[:300]
                log.warning(
                    "office-file wrote %s but zalo send failed: %s",
                    dest.name,
                    type(e).__name__,
                )
            files.append(
                {
                    "file": dest.name,
                    "ext": dest.suffix.lower(),
                    "zalo": zalo,
                    "zalo_error": zalo_error,
                }
            )

        first = files[0]
        return {
            "ok": True,
            "file": first["file"],
            "ext": first["ext"],
            "files": files,
            "zalo": first.get("zalo"),
            "zalo_error": first.get("zalo_error"),
        }
