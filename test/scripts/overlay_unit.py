# -*- coding: utf-8 -*-
"""Unit: dispatcher overlay paints caller-supplied lines (no VPS)."""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "dispatcher"))

from overlay import apply_overlay, clean_overlay_lines  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    if clean_overlay_lines(["  E5 RON92: 21.000  ", "", "E10 RON95: 22.000"]) != [
        "E5 RON92: 21.000",
        "E10 RON95: 22.000",
    ]:
        print("FAIL clean_overlay_lines")
        return 1
    if clean_overlay_lines(["a"] * 20) != ["a"] * 6:
        print("FAIL overlay line cap")
        return 1
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("SKIP overlay render (no Pillow)")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "scene.jpg"
        Image.new("RGB", (640, 360), (40, 80, 120)).save(p, quality=90)
        before = p.stat().st_size
        apply_overlay(p, ["Tp.HCM u ám", "E5 RON92: 21.000"])
        if p.stat().st_size <= 0 or not p.is_file():
            print("FAIL overlay wrote empty")
            return 1
        if p.stat().st_size == before:
            print("FAIL overlay did not change file")
            return 1
        tiny = Path(tmp) / "tiny.jpg"
        Image.new("RGB", (160, 90), (20, 40, 60)).save(tiny, quality=90)
        apply_overlay(tiny, ["E5 RON92 21000dong/lit va E10 RON95 22000dong/lit cap nhat hom nay tai HCMC"])
        im = Image.open(tiny)
        if im.size != (160, 90):
            print("FAIL overlay changed canvas")
            return 1
        from overlay import wrap_text_to_width  # noqa: E402
        d = ImageDraw.Draw(im)
        font = ImageFont.load_default()
        wrapped = wrap_text_to_width("abcdefg hijklmnopqrstuvwxyz", font, 40, d)
        if not wrapped:
            print("FAIL wrap empty")
            return 1
        for line in wrapped:
            bbox = d.textbbox((0, 0), line, font=font)
            if bbox[2] - bbox[0] > 48:
                print("FAIL wrap overflow")
                return 1
    print("PASS overlay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
