# -*- coding: utf-8 -*-
"""Pillow /v1/overlay badge rejects placeholders and paints bottom-left."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISP = ROOT / "architect" / "models" / "dispatcher"
sys.path.insert(0, str(DISP))

from overlay import apply_overlay, clean_overlay_lines  # noqa: E402

OUT = ROOT / "scripts" / "temp" / "overlay_unit"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cleaned = clean_overlay_lines(
        [
            "Nhiệt độ: <value after search>",
            "SCENE: Ho Chi Minh City",
            "Nhiệt độ: 29°C",
            "Độ ẩm: 70%",
        ]
    )
    assert cleaned == ["Nhiệt độ: 29°C", "Độ ẩm: 70%"], cleaned

    from PIL import Image

    img = OUT / "badge.jpg"
    Image.new("RGB", (960, 540), (40, 80, 120)).save(img, quality=90)
    apply_overlay(img, cleaned, corner="bottom-left")
    assert img.stat().st_size > 4000
    print("OVERLAY_UNIT_OK", len(cleaned), img.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
