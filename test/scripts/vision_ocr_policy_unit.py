# -*- coding: utf-8 -*-
"""Unit: vision-ocr-only policy via shared lib (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def test_lib_vision_only() -> None:
    src = (ROOT / "architect" / "lib" / "vision_ocr.py").read_text(encoding="utf-8")
    if "paddle_engine" in src or "PaddleOCR" in src or "tesseract" in src.lower():
        raise SystemExit("FAIL legacy paddle/tesseract still referenced in vision_ocr.py")
    if "vision-ocr" not in src:
        raise SystemExit("FAIL vision-ocr missing from vision_ocr.py")
    if "vision_read_path" not in src:
        raise SystemExit("FAIL vision_read_path helper missing")
    ocr_dir = ROOT / "architect" / "tools" / "ocr"
    if ocr_dir.exists():
        raise SystemExit("FAIL architect/tools/ocr still present")
    print("OK lib vision-only policy")


def test_empty_scan() -> None:
    sys.path.insert(0, str(ROOT / "architect" / "lib"))
    from vision_ocr import empty_scan_result  # noqa: E402

    r = empty_scan_result("vision-ocr")
    if not r.get("ok") or not r.get("empty") or r.get("text") != "":
        raise SystemExit(f"FAIL empty_scan={r!r}")
    print("OK empty scan helper")


def test_path_resolution_opt_data() -> None:
    import tempfile
    import shutil

    sys.path.insert(0, str(ROOT / "architect" / "lib"))
    from vision_ocr import resolve_media_path  # noqa: E402

    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "opt" / "data" / "media" / "inbound" / "dm" / "probe.jpg"
        fake.parent.mkdir(parents=True, exist_ok=True)
        fake.write_bytes(b"\xff\xd8\xff\xd9")
        # Simulate Hermes path while file lives under temp opt/data tree
        import os

        os.environ["OCR_MEDIA_ROOT"] = str(Path(td) / "opt" / "data" / "media")
        resolved = resolve_media_path("/opt/data/media/inbound/dm/probe.jpg")
        if resolved is None or not resolved.is_file():
            raise SystemExit(f"FAIL resolve /opt/data/media path got {resolved!r}")
    print("OK /opt/data/media path resolution")


def main() -> int:
    test_lib_vision_only()
    test_empty_scan()
    test_path_resolution_opt_data()
    print("PASS vision_ocr_policy_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
