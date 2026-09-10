# -*- coding: utf-8 -*-
"""Regression: visual-PDF gate distinguishes positive output and audit lines."""
from __future__ import annotations

from visual_weather_pdf_gate import (
    blocking_defects_clear,
    delivered_image_count,
    extracted_pdf_text,
    new_pdf_seen,
    unrequested_current_scope_terms,
    visual_quality_score,
)


def main() -> int:
    assert not new_pdf_seen("NO_NEW_PDF\n/old/file.pdf")
    assert new_pdf_seen("NEW_PDF /data/assistant/media/out/fresh.pdf")
    assert delivered_image_count("DELIVERED_IMAGE_COUNT 0") == 0
    assert delivered_image_count("DELIVERED_IMAGE_COUNT 2\n") == 2
    assert delivered_image_count("DELIVERED_IMAGE_COUNT_QUERY_FAILED query_error") is None
    assert visual_quality_score("QUALITY_SCORE: 8/10") == 8
    assert visual_quality_score("**Rating: 6/10**") == 6
    assert visual_quality_score("looks good") is None
    assert blocking_defects_clear("BLOCKING_DEFECTS: none")
    assert not blocking_defects_clear("BLOCKING_DEFECTS: text overlap")
    assert not blocking_defects_clear("no structured verdict")
    assert extracted_pdf_text(
        "PDF_TEXT_BEGIN\nCurrent weather\nPDF_TEXT_END\nBLOCKING_DEFECTS: none"
    ) == "Current weather"
    assert extracted_pdf_text("PDF_TEXT_CHARS 42") == ""
    assert unrequested_current_scope_terms("Trời mưa, nếu ra ngoài bạn nên mang theo ô") == [
        "nếu ra ngoài",
        "nên mang",
    ]
    assert unrequested_current_scope_terms("Nhiệt độ hiện tại 27°C") == []
    print("visual_weather_pdf_gate_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
