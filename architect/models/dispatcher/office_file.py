"""Office file create + Zalo send. Enable: OFFICE_FILE_GEN=1 (Medium+ via profile)."""
from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

log = logging.getLogger("office_file")

_OFFICE_OK = {".txt", ".csv", ".md", ".xlsx", ".docx", ".pdf"}

# Prefer Unicode TTFs so Vietnamese PDF does not fall back to .txt
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
)

_OFFICE_KIND = re.compile(
    r"\b(pdf|docx|xlsx|csv|txt|text|markdown|\.md)\b",
    re.I,
)
# Multi-kind gate only (skip single-shot shortcut). Classify LLM owns task split.


class OfficeFileReq(BaseModel):
    prompt: str = ""
    thread_id: str = ""
    thread_type: str = "user"
    caption: str = ""
    filename: Optional[str] = None


def _enabled() -> bool:
    # Default off (Low). Medium+ sets OFFICE_FILE_GEN=1 via profile.sh / compose.
    v = (
        os.environ.get("OFFICE_FILE_GEN") or os.environ.get("ZALO_OFFICE_FILE") or "0"
    ).strip().lower()
    return v not in {"0", "false", "no", "off"}


def _norm_office_kind(token: str) -> str:
    t = (token or "").lower().lstrip(".")
    if t in {"text", "txt"}:
        return "txt"
    if t in {"md", "markdown"}:
        return "md"
    return t


def is_compound_office_request(text: str) -> bool:
    """True when 2+ distinct office kinds appear — skip single-shot shortcut.

    Conjunction/clause splitting is classify's job (LLM). This only detects
    multi-kind prompts so the Zalo shortcut does not swallow a compound ask.
    """
    raw = (text or "").strip()
    if not raw:
        return False
    kinds = {_norm_office_kind(k) for k in _OFFICE_KIND.findall(raw)}
    return len(kinds) >= 2


def _office_ext(low: str) -> str:
    if re.search(r"xlsx|excel|\.xls", low):
        return ".xlsx"
    if re.search(r"\bcsv\b", low):
        return ".csv"
    if re.search(r"docx|word|\.doc\b", low):
        return ".docx"
    if re.search(r"\bpdf\b", low):
        return ".pdf"
    if re.search(r"\bmd\b|markdown", low):
        return ".md"
    if re.search(r"\b(?:txt|text)\b", low):
        return ".txt"
    return ".txt"


def _clean_office_body(raw: str, body: str) -> str:
    """Prefer 'chứa số N' payload; strip trailing delivery phrases only."""
    compact = re.search(
        r"(?:ch[uứ]a|chua|contain|đi[eề]n|dien)\s+(?:số|so)\s+(\S+)",
        raw,
        re.I,
    )
    if compact:
        body = compact.group(1).strip().strip(",.;")
    else:
        # Compound tails are classify's job; only strip delivery phrases here.
        body = re.sub(r"^(số|so)\s+", "", body, flags=re.I).strip()
        body = re.sub(
            r"\s*(?:và\s+)?(?:gửi|gui|send|gởi)\s+(?:cho\s+)?(?:tôi|toi|me)\s*$",
            "",
            body,
            flags=re.I,
        ).strip()
        body = re.sub(r"\s+và\s*$", "", body, flags=re.I).strip()

    m2 = re.search(
        r"(\d+)\s*dòng\s*(in\s*hoa)?\s*[\"“]?(.+?)[\"”]?\s*$",
        body,
        re.I | re.S,
    )
    if m2:
        n = max(1, min(int(m2.group(1)), 100))
        line = (m2.group(3) or "").strip().strip('"').strip("'")
        if m2.group(2):
            line = line.upper()
        body = "\n".join([line] * n)

    if not body:
        body = " "
    return body


def parse_office(prompt: str) -> tuple[str, str]:
    """Return (ext, body). UTF-8 Vietnamese prompts."""
    raw = (prompt or "").strip()
    low = raw.lower()
    ext = _office_ext(low)

    body = raw
    m = re.search(
        r"(?:đi[eề]n|dien|ghi|vi[eế]t|viet|ch[uứ]a|chua|contain|n[oộ]i dung|noi dung)"
        r"\s*(?:vào|vao|:)?\s*(.+)$",
        raw,
        re.I | re.S,
    )
    if m:
        body = m.group(1).strip()
    else:
        # "tạo file pdf chỉ số 1" / "... so 1" without điền/chứa
        m_num = re.search(r"(?:ch[iỉ]\s+)?(?:số|so)\s+(.+)$", raw, re.I | re.S)
        if m_num:
            body = m_num.group(1).strip()

    return ext, _clean_office_body(raw, body)


def parse_office_jobs(prompt: str) -> list[tuple[str, str]]:
    """One office prompt → one job.

    Compound multi-file asks are split by classify into separate instructions;
    each instruction hits /v1/office-file once. Do not regex-split compounds here.
    """
    raw = (prompt or "").strip()
    if not raw:
        return []
    return [parse_office(raw)]


def _pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in _FONT_CANDIDATES:
        if Path(path).is_file():
            name = "OfficeSans"
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception as e:  # noqa: BLE001
                log.warning("pdf font register failed %s: %s", path, e)
    return "Helvetica"


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
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas

            font = _pdf_font()
            c = canvas.Canvas(str(dest), pagesize=A4)
            c.setFont(font, 12)
            y = 800
            for line in body.splitlines() or [body]:
                # reportlab drawString needs str; Unicode OK with TTFont
                c.drawString(72, y, line[:110])
                y -= 16
                if y < 72:
                    c.showPage()
                    c.setFont(font, 12)
                    y = 800
            c.save()
            return dest
        except Exception as e:  # noqa: BLE001
            log.warning("pdf write failed, fallback txt: %s", e)
            dest = dest.with_suffix(".txt")
            dest.write_text(body + "\n", encoding="utf-8")
            return dest
    dest.write_text(body + "\n", encoding="utf-8")
    return dest


def register_office_file(
    app: FastAPI,
    media_dir: Path,
    deliver: Callable[..., dict[str, Any]],
) -> None:
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

        jobs = parse_office_jobs(prompt)
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
            except HTTPException as e:
                # File is on disk under media/out — Hermes autosend can still deliver.
                zalo_error = e.detail
                log.warning(
                    "office-file wrote %s but zalo send failed: %s",
                    dest.name,
                    e.detail,
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
