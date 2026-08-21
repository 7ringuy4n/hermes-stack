# -*- coding: utf-8 -*-
"""Unit: PaddleOCR result normalization + primary-engine policy (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "tools" / "ocr"))

from paddle_engine import _lines_from_result  # noqa: E402
from result import empty_scan_result  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def test_lines_from_v2_shape() -> None:
    # Classic paddleocr 2.x page shape
    page = [
        [[[0, 0], [1, 0], [1, 1], [0, 1]], ("HOA DON 1250000", 0.98)],
        [[[0, 0], [1, 0], [1, 1], [0, 1]], ("VND", 0.91)],
        [[[0, 0], [1, 0], [1, 1], [0, 1]], ("noise", 0.1)],  # below threshold
    ]
    lines = _lines_from_result([page])
    if lines != ["HOA DON 1250000", "VND"]:
        raise SystemExit(f"FAIL v2 lines={lines!r}")
    print("OK v2 result shape")


def test_lines_from_v3_dict() -> None:
    class Fake:
        def get(self, k, default=None):
            return {"rec_texts": ["Xin chao", "123"], "rec_scores": [0.99, 0.95]}.get(k, default)

    lines = _lines_from_result([Fake()])
    if lines != ["Xin chao", "123"]:
        raise SystemExit(f"FAIL v3 lines={lines!r}")
    print("OK v3 result shape")


def test_empty_scan() -> None:
    r = empty_scan_result("paddle")
    if not r.get("ok") or not r.get("empty") or r.get("text") != "":
        raise SystemExit(f"FAIL empty_scan={r!r}")
    print("OK empty scan helper")


def test_app_defaults_paddle_first() -> None:
    # Import after path is set; avoid loading paddle wheels.
    import importlib

    # Force vision off / paddle on via env before import side effects — app already
    # reads env at import time, so read the source contract instead.
    src = (ROOT / "architect" / "tools" / "ocr" / "app.py").read_text(encoding="utf-8")
    if 'OCR_VISION") or "0"' not in src and 'OCR_VISION") or "0"' not in src.replace(" ", ""):
        # looser check
        if 'os.environ.get("OCR_VISION") or "0"' not in src:
            raise SystemExit("FAIL OCR_VISION default is not 0")
    if "paddle_engine.extract_text" not in src and "_paddle_image" not in src:
        raise SystemExit("FAIL paddle primary path missing")
    if "Primary: PaddleOCR" not in src and "primary: PaddleOCR" not in src.lower():
        # comment in module docstring
        if "PaddleOCR first" not in src:
            raise SystemExit("FAIL paddle-first docstring missing")
    # Vision must not run unless VISION is true — check default gate
    if "if VISION and is_image" not in src and "if VISION and" not in src:
        raise SystemExit("FAIL vision is not gated behind VISION")
    print("OK app defaults paddle-first, vision opt-in")
    del importlib


def main() -> int:
    test_lines_from_v2_shape()
    test_lines_from_v3_dict()
    test_empty_scan()
    test_app_defaults_paddle_first()
    print("PASS paddle_ocr_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
