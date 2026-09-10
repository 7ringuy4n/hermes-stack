# -*- coding: utf-8 -*-
"""Pure result parsing shared by the visual-weather PDF live gate and unit."""
from __future__ import annotations

import re


def new_pdf_seen(text: str) -> bool:
    """Require the positive line token; ``NO_NEW_PDF`` must never match."""
    return bool(re.search(r"(?m)^NEW_PDF\s+\S+", text or ""))


def delivered_image_count(text: str) -> int | None:
    """Return the durable delivery count, or None when the audit failed."""
    match = re.search(r"(?m)^DELIVERED_IMAGE_COUNT\s+(\d+)\s*$", text or "")
    return int(match.group(1)) if match else None


def visual_quality_score(text: str) -> float | None:
    """Read the judge's explicit score, accepting the legacy Rating label."""
    match = re.search(
        r"(?im)(?:QUALITY_SCORE\s*:|Rating\s*:)\s*\*{0,2}\s*(\d+(?:\.\d+)?)\s*/\s*10",
        text or "",
    )
    return float(match.group(1)) if match else None


def blocking_defects_clear(text: str) -> bool:
    """Require the structured visual judge to explicitly report no blocker."""
    match = re.search(r"(?im)^BLOCKING_DEFECTS\s*:\s*(.+?)\s*$", text or "")
    return bool(match and match.group(1).strip().lower() == "none")


def extracted_pdf_text(text: str) -> str:
    """Return only rendered-PDF text, excluding judge and runtime commentary."""
    if "PDF_TEXT_BEGIN" not in text or "PDF_TEXT_END" not in text:
        return ""
    return text.split("PDF_TEXT_BEGIN", 1)[1].split("PDF_TEXT_END", 1)[0].strip()


def unrequested_current_scope_terms(text: str) -> list[str]:
    """Identify forecast/recommendation copy forbidden in a current-only PDF."""
    lower = (text or "").lower()
    forbidden = (
        "dự báo 4 ngày",
        "khả năng mưa",
        "khuyến nghị",
        "nếu ra ngoài",
        "nên mang",
        "hãy mang",
        "mang theo áo mưa",
    )
    return [phrase for phrase in forbidden if phrase in lower]
