# -*- coding: utf-8 -*-
"""Regression: visual-PDF gate distinguishes positive output and audit lines."""
from __future__ import annotations

import os

# deploy_stack validates its transport environment at import time. This unit
# never connects; harmless placeholders keep the pure parser import isolated.
os.environ.setdefault("ASSISTANT_SSH_HOST", "unit.invalid")
os.environ.setdefault("ASSISTANT_SSH_USER", "unit")
os.environ.setdefault("ASSISTANT_SSH_PASSWORD", "unit")

from zalo_tn_visual_weather_pdf_inject import (
    _delivered_image_count,
    _new_pdf_seen,
)


def main() -> int:
    assert not _new_pdf_seen("NO_NEW_PDF\n/old/file.pdf")
    assert _new_pdf_seen("NEW_PDF /data/assistant/media/out/fresh.pdf")
    assert _delivered_image_count("DELIVERED_IMAGE_COUNT 0") == 0
    assert _delivered_image_count("DELIVERED_IMAGE_COUNT 2\n") == 2
    assert _delivered_image_count("DELIVERED_IMAGE_COUNT_QUERY_FAILED query_error") is None
    print("visual_weather_pdf_gate_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
