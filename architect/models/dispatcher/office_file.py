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

    def _marker_at(upper: str, marker: str, start: int = 0) -> int:
        """Index of marker not mid-token (avoids TITLE: inside SUBTITLE:)."""
        i = start
        while True:
            j = upper.find(marker, i)
            if j < 0:
                return -1
            if j == 0 or not upper[j - 1].isalnum():
                return j
            i = j + 1

    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        upper = line.upper()
        # Mid-line contract markers after a create-verb wrapper
        cut = -1
        for marker in ("SUBTITLE:", "TITLE:", "ICON:"):
            mi = _marker_at(upper, marker)
            if mi > 0:
                cut = mi if cut < 0 else min(cut, mi)
        if cut > 0:
            line = line[cut:]
            upper = line.upper()

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
            if "|" in icon:
                icon = icon.split("|", 1)[0].strip() or "sun"
            continue
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
        if kind == "storm":
            c.setFillColor(Color(1.0, 0.85, 0.2))
            c.line(cx + 4 * scale, cy + 8 * scale, cx - 6 * scale, cy - 18 * scale)
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


def _wrap_text(text: str, font_name: str, size: int, max_width: float, c: Any) -> list[str]:
    """Word-wrap for reportlab canvas (width in points)."""
    words = (text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if c.stringWidth(trial, font_name, size) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


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


def _hero_temp(facts: list[str]) -> str:
    """Pick a Celsius temperature for the header (never wind bearings like 246°WSW)."""
    labeled: list[str] = []
    unlabeled: list[str] = []
    for fact in facts:
        label = ""
        value = fact
        if ": " in fact:
            label, value = fact.split(": ", 1)
        elif ":" in fact and fact.index(":") < 40:
            label, value = fact.split(":", 1)
        low_l = label.lower().strip()
        target = labeled if any(
            x in low_l for x in ("nhiệt", "temp", "feels", "cảm giác")
        ) else unlabeled
        for token in value.replace(",", " ").split():
            t = token.strip().strip(".,;")
            if not t:
                continue
            # Reject compass bearings (246°WSW)
            if "°" in t or "º" in t:
                sep = "°" if "°" in t else "º"
                after = t.split(sep, 1)[1].upper()
                if after and after[0].isalpha() and not after.startswith(("C", "F")):
                    continue
            if t.endswith(("°C", "ºC")) or "℃" in t:
                target.append(t if "°" in t or "℃" in t else f"{t}°C")
                continue
            # bare number on a temperature-labeled row → append °C
            core = t
            if core.replace(".", "", 1).isdigit() and any(
                x in low_l for x in ("nhiệt", "temp", "feels", "cảm giác")
            ):
                target.append(f"{core}°C")
    if labeled:
        return labeled[0]
    if unlabeled:
        return unlabeled[0]
    return ""


def write_pdf_styled(dest: Path, body: str) -> Path:
    """Attractive one-page weather/info card PDF (header, vector icon, fact rows)."""
    from reportlab.lib.colors import Color, white
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    meta = parse_styled_pdf_body(body)
    font = _pdf_font()
    bold = _pdf_font_bold()
    width, height = A4
    c = canvas.Canvas(str(dest), pagesize=A4)

    header_h = 168
    accent = Color(0.12, 0.45, 0.78)
    accent_deep = Color(0.08, 0.32, 0.58)
    if meta["icon"] in {"rain", "storm", "mưa", "mua"}:
        accent = Color(0.22, 0.38, 0.62)
        accent_deep = Color(0.14, 0.26, 0.48)
    elif meta["icon"] in {"sun", "clear", "nắng", "nang", "sunny"}:
        accent = Color(0.18, 0.58, 0.88)
        accent_deep = Color(0.10, 0.42, 0.72)
    elif meta["icon"] in {"cloud", "cloudy", "mây", "may", "overcast"}:
        accent = Color(0.35, 0.48, 0.62)
        accent_deep = Color(0.22, 0.34, 0.48)

    # Full-bleed soft background + subtle top wash
    c.setFillColor(Color(0.93, 0.95, 0.98))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(Color(0.88, 0.92, 0.97))
    c.rect(0, height - 220, width, 220, fill=1, stroke=0)

    # Header band
    c.setFillColor(accent)
    c.roundRect(32, height - header_h - 28, width - 64, header_h, 20, fill=1, stroke=0)
    c.setFillColor(accent_deep)
    c.roundRect(32, height - header_h - 28, 10, header_h, 4, fill=1, stroke=0)

    # Icon on the right of header
    _draw_weather_icon(c, meta["icon"], width - 108, height - 100, scale=1.35)

    # Title / subtitle on header (wrapped)
    c.setFillColor(white)
    title_font = bold if bold != "Helvetica" else font
    title_lines = _wrap_text(meta["title"][:90], title_font, 18, width - 220, c)[:2]
    ty = height - 64
    c.setFont(title_font, 18)
    for tl in title_lines:
        c.drawString(56, ty, tl)
        ty -= 22
    sub = (meta["subtitle"] or "Cập nhật trực tiếp")[:90]
    c.setFont(font, 11)
    c.drawString(56, ty - 4, sub)

    hero = _hero_temp(meta["facts"] or [])
    if hero:
        c.setFont(title_font, 28)
        c.drawRightString(width - 150, height - 150, hero)

    # Fact card
    card_top = height - header_h - 52
    card_bottom = 64
    c.setFillColor(white)
    c.setStrokeColor(Color(0.78, 0.84, 0.90))
    c.setLineWidth(1.2)
    c.roundRect(40, card_bottom, width - 80, card_top - card_bottom, 16, fill=1, stroke=1)

    y = card_top - 40
    facts = meta["facts"] or ["(no details)"]
    max_text_w = width - 180
    for i, fact in enumerate(facts[:12]):
        if y < card_bottom + 36:
            break
        label, value = _split_label_value(fact)
        # Estimate row height from wrapped value
        show = value if not label else value
        wrap = _wrap_text(show[:120], font, 11, max_text_w - (90 if label else 0), c)[:3]
        row_h = max(34, 14 + 14 * len(wrap))
        if i % 2 == 0:
            c.setFillColor(Color(0.95, 0.97, 1.0))
            c.roundRect(52, y - row_h + 18, width - 104, row_h, 8, fill=1, stroke=0)
        # accent pill
        c.setFillColor(accent)
        c.roundRect(60, y - 2, 6, 14, 3, fill=1, stroke=0)
        c.setFillColor(Color(0.12, 0.18, 0.28))
        text_x = 78
        if label:
            c.setFont(title_font, 10)
            c.setFillColor(accent_deep)
            c.drawString(text_x, y, label[:28])
            c.setFillColor(Color(0.12, 0.18, 0.28))
            c.setFont(font, 11)
            vx = text_x + 96
            for wi, wl in enumerate(wrap):
                c.drawString(vx, y - wi * 13, wl)
        else:
            c.setFont(font, 11)
            for wi, wl in enumerate(wrap):
                c.drawString(text_x, y - wi * 13, wl)
        y -= row_h + 6

    # Footer
    c.setStrokeColor(accent)
    c.setLineWidth(2.5)
    c.line(48, 48, width - 48, 48)
    c.setFillColor(Color(0.40, 0.48, 0.58))
    c.setFont(font, 8)
    c.drawString(48, 34, "Bản tin thời tiết")

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
