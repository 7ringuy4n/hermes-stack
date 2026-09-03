# -*- coding: utf-8 -*-
"""Weather overlay lines + Pillow corner badge (no LLM)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZALO = ROOT / "hermes" / "main" / "plugins" / "zalo"
DISP = ROOT / "architect" / "models" / "dispatcher"
sys.path.insert(0, str(ZALO))
sys.path.insert(0, str(DISP))

from media_shortcuts import _weather_overlay_lines  # noqa: E402
from overlay import apply_overlay  # noqa: E402

OUT = ROOT / "scripts" / "temp" / "weather_overlay_unit"
VI_SAMPLE = "Thành phố Hồ Chí Minh"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    facts = [
        "Nhiệt độ: 28°C",
        "Độ ẩm: 83%",
        "Tình trạng: mây dần tăng",
        "Gió: 12 km/h",
    ]
    lines = _weather_overlay_lines(
        facts,
        scene="SCENE: Ho Chi Minh City skyline at dusk",
        user_ask="thời tiết hồ chí minh",
    )
    assert any(VI_SAMPLE in ln for ln in lines), lines
    assert all("Thổi" not in ln and "Thời thết" not in ln for ln in lines), lines
    assert any("Nhiệt độ" in ln for ln in lines), lines
    assert any("Cập nhật:" in ln for ln in lines), lines

    from PIL import Image

    img = OUT / "scene.jpg"
    Image.new("RGB", (1280, 720), (90, 120, 160)).save(img, quality=90)
    apply_overlay(img, lines, corner="bottom-left")
    assert img.stat().st_size > 5000, img.stat().st_size
    print("WEATHER_OVERLAY_OK", len(lines), img)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
