# -*- coding: utf-8 -*-
"""Unit: a chat reply that never saw the image must not pass as OCR text (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "tools" / "ocr"))

from refuse import llm_refused  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Verbatim replies seen from the lab router when the routed model has no vision.
BLIND = [
    "I don\u2019t see an image or file attached. Please upload the image, and I\u2019ll "
    "extract all visible text as markdown.",
    "I'd be happy to help extract text as markdown, but you haven't provided any "
    "source material for me to extract text from.",
    "I don't see any image attached to your message. Could you please share the image?",
    "Please provide the image or document you would like me to process!",
    "Once you share the source, I'll extract all visible text and format it as markdown.",
    "I cannot process images — I'm just a language model.",
]

REAL = [
    "HOA DON 1250000 VND",
    "| Ngay | So tien |\n| 01/08 | 250.000 |",
    "Invoice total: 1,250,000 VND\nCustomer: Nguyen Van A",
]


def test_blind_replies_refused() -> None:
    for reply in BLIND:
        if not llm_refused(200, "", reply):
            raise SystemExit(f"FAIL blind reply accepted as OCR text: {reply[:60]!r}")
    print(f"OK blind replies refused ({len(BLIND)})")


def test_real_text_kept() -> None:
    for text in REAL:
        if llm_refused(200, "", text):
            raise SystemExit(f"FAIL real OCR text refused: {text[:60]!r}")
    print(f"OK extracted text kept ({len(REAL)})")


def test_upstream_status() -> None:
    for status in (413, 422, 502):
        if not llm_refused(status, "", "HOA DON"):
            raise SystemExit(f"FAIL status {status} not treated as failure")
    if llm_refused(200, "", "HOA DON 1250000 VND"):
        raise SystemExit("FAIL 200 with clean text treated as failure")
    print("OK upstream status handling")


def main() -> int:
    test_blind_replies_refused()
    test_real_text_kept()
    test_upstream_status()
    print("PASS ocr_refuse_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
