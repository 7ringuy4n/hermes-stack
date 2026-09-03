"""Office file create + Zalo send. Enable: OFFICE_FILE_GEN=active (compose / Media worker)."""
from __future__ import annotations

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

# Prefer Unicode TTFs so Vietnamese PDF does not fall back to .txt
# (resolved via fonts.py — bundled Noto Sans first).
_FONT_CANDIDATES = ()  # legacy unused; kept for import compatibility
_FONT_BOLD_CANDIDATES = ()

# Structured markers Hermes may put in legacy office prompts (markdown preferred).

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
    # Default off; Media worker / compose sets OFFICE_FILE_GEN=active when office create is on.
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


def _register_font(candidates: tuple[str, ...], name: str) -> str:
    del candidates, name
    from fonts import reportlab_font_name

    return reportlab_font_name(bold=False)


def _pdf_font() -> str:
    from fonts import reportlab_font_name

    return reportlab_font_name(bold=False)


def _pdf_font_bold() -> str:
    from fonts import reportlab_font_name

    return reportlab_font_name(bold=True)


def _skip_structural_junk(line: str) -> bool:
    """Drop empty lines, URLs, JSON blobs, placeholders, and markdown table chrome."""
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
    if "<" in s or ">" in s:
        return True
    if "value after" in low:
        return True
    if "safe-for-work" in low or "safe for work" in low:
        return True
    # Markdown table separator / empty pipe rows: |---|---|
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


def _split_label_value(fact: str) -> tuple[str, str]:
    s = (fact or "").strip()
    if ": " in s:
        left, right = s.split(": ", 1)
        if 1 <= len(left) <= 40 and right.strip():
            return left.strip(), right.strip()
    if ":" in s and s.index(":") < 40:
        left, right = s.split(":", 1)
        if right.strip():
            return left.strip(), right.strip()
    return "", s


def _hero_metric(facts: list[str]) -> str:
    """First labeled value with ° or % — keep the short token before '('."""
    for fact in facts:
        _label, value = _split_label_value(fact)
        src = (value or fact).strip()
        if "°" not in src and "%" not in src:
            continue
        token = src
        for sep in ("(", "（", " - ", " — "):
            if sep in token:
                token = token.split(sep, 1)[0].strip()
        if token and len(token) <= 16:
            return token
        # Prefer leading number+unit (e.g. 27°C) when the value is long.
        words = token.split()
        if words:
            first = words[0].strip(" ,;")
            if "°" in first or "%" in first:
                return first[:12]
        if token:
            return token[:12]
    return ""


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


def write_pdf_styled(dest: Path, body: str) -> Path:
    """Render LLM markdown: full-bleed hero IMAGE:, title band, 2-col fact cards, prose."""
    from reportlab.lib.colors import Color, white
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    font = _pdf_font()
    bold = _pdf_font_bold()
    title_font = bold if bold != "Helvetica" else font
    width, height = A4
    margin = 40
    accent = Color(0.10, 0.42, 0.78)
    accent_soft = Color(0.90, 0.95, 0.99)
    card = Color(0.97, 0.98, 1.0)
    text = Color(0.10, 0.16, 0.26)
    muted = Color(0.42, 0.48, 0.56)
    page_bg = Color(0.94, 0.96, 0.99)

    hero_path: Path | None = None
    title = ""
    subtitle = ""
    facts: list[str] = []
    prose: list[str] = []

    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("image:"):
            hero_path = _resolve_pdf_image(line.split(":", 1)[1].strip())
            continue
        if line.startswith("#"):
            hashes = 0
            while hashes < len(line) and line[hashes] == "#":
                hashes += 1
            rest = line[hashes:].strip()
            if hashes == 1 and rest:
                title = rest
                continue
            if hashes == 2 and rest:
                subtitle = rest
                continue
            if rest:
                prose.append(rest)
            continue
        if line.startswith(("- ", "• ", "* ")):
            item = line[2:].strip()
            if item and not _skip_structural_junk(item):
                facts.append(item)
            continue
        if _skip_structural_junk(line):
            continue
        prose.append(line)

    if not title and prose:
        title = prose.pop(0)[:72]
    if not title:
        title = "Báo cáo"

    c = canvas.Canvas(str(dest), pagesize=A4)
    c.setFillColor(page_bg)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    y = height

    hero_ok = False
    if hero_path and hero_path.is_file():
        img_h = 260
        try:
            c.drawImage(
                str(hero_path),
                0,
                y - img_h,
                width=width,
                height=img_h,
                preserveAspectRatio=True,
                anchor="n",
            )
            # Soft fade into page at bottom of hero
            c.setFillColor(page_bg)
            c.rect(0, y - img_h, width, 28, fill=1, stroke=0)
            y -= img_h + 8
            hero_ok = True
        except Exception as e:  # noqa: BLE001
            log.warning("pdf hero image skipped: %s", type(e).__name__)
            y = height - margin

    if not hero_ok:
        y = height - margin

    band_h = 78 if subtitle else 58
    c.setFillColor(accent)
    c.roundRect(margin, y - band_h, width - 2 * margin, band_h, 14, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(title_font, 20)
    c.drawString(margin + 18, y - 28, title[:52])
    if subtitle:
        c.setFont(font, 11)
        c.drawString(margin + 18, y - 50, subtitle[:64])
    y -= band_h + 18

    hero_val = _hero_metric(facts)
    if hero_val:
        c.setFillColor(accent)
        c.setFont(title_font, 36)
        c.drawString(margin + 4, y - 8, hero_val[:20])
        y -= 48

    # Two-column metric cards
    col_gap = 12
    col_w = (width - 2 * margin - col_gap) / 2
    card_h = 64
    col = 0
    row_y = y
    for fact in facts[:10]:
        label, value = _split_label_value(fact)
        if hero_val and value and value.split("(", 1)[0].strip() == hero_val.strip():
            continue
        if row_y - card_h < 72:
            c.showPage()
            c.setFillColor(page_bg)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            row_y = height - margin
            col = 0
        x0 = margin + col * (col_w + col_gap)
        c.setFillColor(card)
        c.setStrokeColor(accent_soft)
        c.setLineWidth(1)
        c.roundRect(x0, row_y - card_h, col_w, card_h, 10, fill=1, stroke=1)
        c.setFillColor(accent)
        c.setFont(title_font, 9)
        c.drawString(x0 + 12, row_y - 16, (label or "•")[:28])
        c.setFillColor(text)
        wrap_src = (value or fact).strip()
        rows = _pdf_wrap_line(c, wrap_src, font, 11, col_w - 24)
        ty = row_y - 34
        for row in rows[:2]:
            c.setFont(font, 11)
            c.drawString(x0 + 12, ty, row)
            ty -= 14
        if col == 0:
            col = 1
        else:
            col = 0
            row_y -= card_h + 10
    if col == 1:
        row_y -= card_h + 10
    y = row_y - 8

    for para in prose[:6]:
        if y < 72:
            c.showPage()
            c.setFillColor(page_bg)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            y = height - margin
        c.setFont(font, 11)
        c.setFillColor(muted)
        for row in _pdf_wrap_line(c, para, font, 11, width - 2 * margin):
            c.drawString(margin, y, row[:110])
            y -= 14
        y -= 6

    c.save()
    return dest


def _resolve_pdf_image(raw: str) -> Path | None:
    p = (raw or "").strip().strip("'").strip('"')
    if not p:
        return None
    candidates: list[Path] = []
    if p.startswith("/"):
        candidates.append(Path(p))
    for base in (
        Path("/opt/data/media/out"),
        Path("/data/assistant/media/out"),
        Path("/opt/data/media/inbound"),
    ):
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


def _pdf_wrap_line(c: Any, text: str, font_name: str, size: int, max_w: float) -> list[str]:
    c.setFont(font_name, size)
    words = text.split()
    if not words:
        return [""]
    rows: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if c.stringWidth(trial, font_name, size) <= max_w:
            cur = trial
        else:
            rows.append(cur)
            cur = w
    rows.append(cur)
    return rows


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
            return write_pdf_styled(dest, body)
        except Exception as e:  # noqa: BLE001
            log.warning("styled pdf failed, plain fallback: %s", e)
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.pdfgen import canvas

                font = _pdf_font()
                c = canvas.Canvas(str(dest), pagesize=A4)
                c.setFont(font, 12)
                y = 800
                for line in body.splitlines() or [body]:
                    c.drawString(72, y, line[:110])
                    y -= 16
                    if y < 72:
                        c.showPage()
                        c.setFont(font, 12)
                        y = 800
                c.save()
                return dest
            except Exception as e2:  # noqa: BLE001
                log.warning("pdf write failed, fallback txt: %s", e2)
                dest = dest.with_suffix(".txt")
                dest.write_text(body + "\n", encoding="utf-8")
                return dest
    if ext == ".pptx":
        try:
            return write_pptx_styled(dest, body)
        except Exception as e:  # noqa: BLE001
            log.warning("pptx write failed, fallback pdf: %s", e)
            dest = dest.with_suffix(".pdf")
            try:
                return write_pdf_styled(dest, body)
            except Exception as e2:  # noqa: BLE001
                log.warning("pptx→pdf fallback failed: %s", e2)
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
                # File is on disk under media/out — Hermes autosend can still deliver.
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
