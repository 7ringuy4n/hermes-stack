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

from media_shortcuts import (  # noqa: E402
    _collect_host_facts,
    _skip_structural_junk,
    _weather_overlay_lines,
)
from overlay import apply_overlay  # noqa: E402

OUT = ROOT / "scripts" / "temp" / "weather_overlay_unit"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    facts = [
        "Nhiệt độ: 28°C",
        "Độ ẩm: 83%",
        "Thời tiết: mây dần tăng",
        "Gió: 12 km/h",
        "Nhiệt đô: <value after search>",
        "SAFE-FOR-WORK",
    ]
    assert _skip_structural_junk("Nhiệt độ: <value after search>")
    assert _skip_structural_junk("SAFE-FOR-WORK")
    assert not _skip_structural_junk("Nhiệt độ: 28°C")

    lines = _weather_overlay_lines(
        facts,
        scene="SAFE-FOR-WORK; photorealistic photograph of Ho Chi Minh City",
        user_ask="cập nhật thông tin thời tiết hồ chí minh lúc này, sau đó ghi thông tin lên hình",
    )
    blob = "\n".join(lines)
    assert "SAFE-FOR-WORK" not in blob.upper().replace("-", ""), lines
    assert "value after" not in blob.lower(), lines
    assert "SCENE:" not in blob, lines
    assert lines[0] == "Nhiệt độ", lines
    assert any("Nhiệt độ" in ln for ln in lines), lines
    assert any("Thời tiết" in ln for ln in lines), lines
    assert any(ln.startswith("Updated:") for ln in lines), lines
    assert "unavailable" not in blob.lower(), lines
    empty = _weather_overlay_lines(
        ["current weather details unavailable"],
        user_ask="cập nhật thông tin thời tiết",
    )
    assert all("unavailable" not in ln.lower() for ln in empty), empty
    assert empty[0] in {"Facts", "cập nhật thông tin thời tiết"}, empty

    collected = _collect_host_facts(
        "RENDER: weather-scene\nSCENE: city\n- Nhiệt độ: <value after search>\n- Độ ẩm: 70%",
        {"answer": "Nhiệt độ: 31°C\nThời tiết: nắng nhẹ"},
    )
    assert all("<" not in x and "value after" not in x.lower() for x in collected), collected
    assert any("31°C" in x or "70%" in x or "nắng" in x for x in collected), collected

    from media_shortcuts import (  # noqa: E402
        _parse_label_value_lines,
        _search_notes_blob,
    )

    notes = _search_notes_blob(
        {
            "answer": None,
            "results": [
                {
                    "title": "ignore title",
                    "content": "Thời tiết hiện tại\n30°C\nNhiều mây\nGió nhẹ 5 km/h\nđộ ẩm 80%",
                }
            ],
        }
    )
    assert "30°C" in notes and "ignore title" not in notes
    parsed = _parse_label_value_lines(
        "Nhiệt độ: 30°C\nĐộ ẩm: 80%\nThời tiết: nhiều mây\nGió: nhẹ 5 km/h\nextra prose"
    )
    assert len(parsed) >= 3
    assert any("30°C" in x for x in parsed)
    assert all(":" in x for x in parsed)

    from PIL import Image

    img = OUT / "scene.jpg"
    Image.new("RGB", (1280, 720), (90, 120, 160)).save(img, quality=90)
    apply_overlay(img, lines, corner="bottom-left")
    assert img.stat().st_size > 5000, img.stat().st_size
    print("WEATHER_OVERLAY_OK", len(lines), img)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
