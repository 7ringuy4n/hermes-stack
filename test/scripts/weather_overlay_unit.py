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
    overlay_heading_from_instruction,
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
        "Updated: 2026-09-04 19:15",
        "Thời gian cập nhật: 19:15",
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
        heading="Ho Chi Minh City Weather",
    )
    blob = "\n".join(lines)
    assert "SAFE-FOR-WORK" not in blob.upper().replace("-", ""), lines
    assert "value after" not in blob.lower(), lines
    assert "SCENE:" not in blob, lines
    assert lines[0] == "Ho Chi Minh City Weather", lines
    assert lines[0] != lines[1].split(":", 1)[0], lines
    assert any("Nhiệt độ" in ln for ln in lines), lines
    assert any("Thời tiết" in ln for ln in lines), lines
    updated = [ln for ln in lines if ln.startswith("Updated:")]
    assert len(updated) == 1, lines
    assert "2026-09-04 19:15" not in blob, lines
    assert "unavailable" not in blob.lower(), lines
    empty = _weather_overlay_lines(
        ["current weather details unavailable"],
        user_ask="cập nhật thông tin thời tiết",
    )
    assert all("unavailable" not in ln.lower() for ln in empty), empty
    assert empty[0] in {"Facts", "cập nhật thông tin thời tiết"}, empty

    marker = (
        "RENDER: live-scene\n"
        "OVERLAY_HEADING: Da Lat Weather\n"
        "SCENE: Da Lat at dusk, photorealistic photograph"
    )
    assert overlay_heading_from_instruction(marker) == "Da Lat Weather"

    collected = _collect_host_facts(
        "RENDER: weather-scene\nSCENE: city\n- Nhiệt độ: <value after search>\n- Độ ẩm: 70%",
        {"answer": "Nhiệt độ: 31°C\nThời tiết: nắng nhẹ"},
    )
    assert all("<" not in x and "value after" not in x.lower() for x in collected), collected
    assert any("31°C" in x or "70%" in x or "nắng" in x for x in collected), collected

    from media_shortcuts import (  # noqa: E402
        _live_scene_visual_prompt,
        _parse_label_value_lines,
        _search_notes_blob,
    )

    visual_prompt = _live_scene_visual_prompt(
        "Da Lat city in natural evening light",
        ["Location: Da Lat, Vietnam", "Temperature: 17.8°C", "Updated: 19:15"],
    )
    assert "Da Lat city" in visual_prompt, visual_prompt
    assert "Location:" not in visual_prompt, visual_prompt
    assert "17.8" not in visual_prompt, visual_prompt
    assert "19:15" not in visual_prompt, visual_prompt
    assert "No readable text" in visual_prompt, visual_prompt

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
