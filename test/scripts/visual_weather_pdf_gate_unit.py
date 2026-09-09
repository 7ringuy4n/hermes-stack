# -*- coding: utf-8 -*-
"""Regression: visual-PDF gate distinguishes positive output and audit lines."""
from __future__ import annotations

from visual_weather_pdf_gate import (
    delivered_image_count,
    new_pdf_seen,
)


def main() -> int:
    assert not new_pdf_seen("NO_NEW_PDF\n/old/file.pdf")
    assert new_pdf_seen("NEW_PDF /data/assistant/media/out/fresh.pdf")
    assert delivered_image_count("DELIVERED_IMAGE_COUNT 0") == 0
    assert delivered_image_count("DELIVERED_IMAGE_COUNT 2\n") == 2
    assert delivered_image_count("DELIVERED_IMAGE_COUNT_QUERY_FAILED query_error") is None
    print("visual_weather_pdf_gate_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
