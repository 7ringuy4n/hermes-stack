"""Office file create + Zalo send. Enable: OFFICE_FILE_GEN=1 (Medium+ via profile)."""
from __future__ import annotations

import logging
import math
import os
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("office_file")

_OFFICE_OK = {".txt", ".csv", ".md", ".xlsx", ".docx", ".pdf"}
_KIND_EXT = {
    "pdf": ".pdf",
    "txt": ".txt",
    "text": ".txt",
    "docx": ".docx",
    "xlsx": ".xlsx",
    "csv": ".csv",
    "md": ".md",
    "markdown": ".md",
}

# Prefer Unicode TTFs so Vietnamese PDF does not fall back to .txt
# (resolved via fonts.py — bundled Noto Sans first).
_FONT_CANDIDATES = ()  # legacy unused; kept for import compatibility
_FONT_BOLD_CANDIDATES = ()

# Structured markers Hermes puts in the office-file prompt (not user NLU).
_TITLE_PREFIXES = ("TITLE:", "Title:", "title:")
_ICON_PREFIXES = ("ICON:", "Icon:", "icon:")
_SUBTITLE_PREFIXES = ("SUBTITLE:", "Subtitle:", "subtitle:")

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
    # Default off (Low). Medium+ sets OFFICE_FILE_GEN=1 via profile.sh / compose.
    v = (
        os.environ.get("OFFICE_FILE_GEN") or os.environ.get("ZALO_OFFICE_FILE") or "0"
    ).strip().lower()
    return v not in {"0", "false", "no", "off"}


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


def _strip_prefix(line: str, prefixes: tuple[str, ...]) -> str | None:
    for p in prefixes:
        if line.startswith(p):
            return line[len(p) :].strip()
    return None


def parse_styled_pdf_body(body: str) -> dict[str, Any]:
    """Parse Hermes-authored TITLE/ICON/SUBTITLE markers; rest are fact lines."""
    title = ""
    subtitle = ""
    icon = "sun"
    facts: list[str] = []
    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        t = _strip_prefix(line, _TITLE_PREFIXES)
        if t is not None:
            title = t
            continue
        s = _strip_prefix(line, _SUBTITLE_PREFIXES)
        if s is not None:
            subtitle = s
            continue
        ic = _strip_prefix(line, _ICON_PREFIXES)
        if ic is not None:
            icon = (ic or "sun").split()[0].lower()
            continue
        # Drop a bare "Icon: foo" already handled; keep bullet/plain facts
        if line.startswith(("- ", "• ", "* ")):
            facts.append(line[2:].strip())
        else:
            facts.append(line)
    if not title and facts:
        title = facts.pop(0)
    return {
        "title": title or "Report",
        "subtitle": subtitle,
        "icon": icon or "sun",
        "facts": facts,
    }


def _draw_weather_icon(c: Any, icon: str, cx: float, cy: float, scale: float = 1.0) -> None:
    """Vector weather motif — no external image API / emoji font required."""
    from reportlab.lib.colors import Color, white

    kind = (icon or "sun").lower()
    r = 28 * scale
    if kind in {"rain", "storm", "mưa", "mua"}:
        c.setFillColor(Color(0.45, 0.55, 0.70))
        c.circle(cx - 12 * scale, cy, 16 * scale, fill=1, stroke=0)
        c.circle(cx + 10 * scale, cy + 4 * scale, 18 * scale, fill=1, stroke=0)
        c.circle(cx, cy - 2 * scale, 20 * scale, fill=1, stroke=0)
        c.setStrokeColor(Color(0.25, 0.40, 0.75))
        c.setLineWidth(2.5 * scale)
        for i in range(4):
            x = cx - 18 * scale + i * 12 * scale
            c.line(x, cy - 22 * scale, x - 4 * scale, cy - 38 * scale)
        return
    if kind in {"cloud", "cloudy", "mây", "may", "overcast"}:
        c.setFillColor(Color(0.75, 0.80, 0.88))
        c.circle(cx - 14 * scale, cy, 18 * scale, fill=1, stroke=0)
        c.circle(cx + 12 * scale, cy + 2 * scale, 20 * scale, fill=1, stroke=0)
        c.circle(cx, cy - 4 * scale, 22 * scale, fill=1, stroke=0)
        return
    # default / sun / clear / nắng
    c.setFillColor(Color(1.0, 0.78, 0.15))
    c.circle(cx, cy, r * 0.55, fill=1, stroke=0)
    c.setStrokeColor(Color(1.0, 0.65, 0.05))
    c.setLineWidth(3 * scale)
    for i in range(8):
        ang = i * math.pi / 4
        c.line(
            cx + math.cos(ang) * r * 0.75,
            cy + math.sin(ang) * r * 0.75,
            cx + math.cos(ang) * r * 1.15,
            cy + math.sin(ang) * r * 1.15,
        )
    c.setFillColor(white)


def write_pdf_styled(dest: Path, body: str) -> Path:
    """Attractive one-page card PDF (header, vector icon, fact rows)."""
    from reportlab.lib.colors import Color, white
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    meta = parse_styled_pdf_body(body)
    font = _pdf_font()
    bold = _pdf_font_bold()
    width, height = A4
    c = canvas.Canvas(str(dest), pagesize=A4)

    header_h = 150
    accent = Color(0.12, 0.45, 0.78)  # sky blue
    if meta["icon"] in {"rain", "storm", "mưa", "mua"}:
        accent = Color(0.25, 0.40, 0.65)
    elif meta["icon"] in {"sun", "clear", "nắng", "nang", "sunny"}:
        accent = Color(0.15, 0.55, 0.85)

    # Full-bleed soft background
    c.setFillColor(Color(0.94, 0.96, 0.99))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Header band
    c.setFillColor(accent)
    c.roundRect(36, height - header_h - 24, width - 72, header_h, 18, fill=1, stroke=0)

    # Icon on the right of header
    _draw_weather_icon(c, meta["icon"], width - 110, height - 90, scale=1.15)

    # Title / subtitle on header
    c.setFillColor(white)
    c.setFont(bold if bold != "Helvetica" else font, 20)
    title = meta["title"][:64]
    c.drawString(56, height - 70, title)
    if meta["subtitle"]:
        c.setFont(font, 11)
        c.drawString(56, height - 92, meta["subtitle"][:80])
    else:
        c.setFont(font, 10)
        c.drawString(56, height - 92, "Live summary")

    # Fact card
    card_top = height - header_h - 48
    card_bottom = 72
    c.setFillColor(white)
    c.setStrokeColor(Color(0.82, 0.86, 0.92))
    c.setLineWidth(1)
    c.roundRect(48, card_bottom, width - 96, card_top - card_bottom, 14, fill=1, stroke=1)

    y = card_top - 36
    facts = meta["facts"] or ["(no details)"]
    row_h = 28
    for i, fact in enumerate(facts[:18]):
        if y < card_bottom + 28:
            break
        if i % 2 == 0:
            c.setFillColor(Color(0.96, 0.98, 1.0))
            c.roundRect(60, y - 8, width - 120, row_h, 6, fill=1, stroke=0)
        c.setFillColor(accent)
        c.circle(78, y + 6, 4, fill=1, stroke=0)
        c.setFillColor(Color(0.15, 0.20, 0.28))
        c.setFont(font, 12)
        c.drawString(96, y, fact[:90])
        y -= row_h + 4

    # Footer accent line
    c.setStrokeColor(accent)
    c.setLineWidth(3)
    c.line(56, 52, width - 56, 52)
    c.setFillColor(Color(0.45, 0.50, 0.58))
    c.setFont(font, 8)
    c.drawString(56, 38, "Designed document")

    c.save()
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
