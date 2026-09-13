#!/usr/bin/env python3
"""Unit: grounded image copy and flexible layout stay in one model prompt."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZALO = ROOT / "hermes" / "main" / "plugins" / "zalo"
sys.path.insert(0, str(ZALO))
spec = importlib.util.spec_from_file_location("media_shortcuts", ZALO / "media_shortcuts.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def main() -> int:
    assert mod._composition_plan_timeout_s() == 120
    assert mod._COMPOSITION_PLAN_MAX_TOKENS == 4096
    assert mod._composition_plan_model() == "classifier"
    os.environ["OMNIROUTER_CLASSIFY_COMBO"] = "structured-planner"
    try:
        assert mod._composition_plan_model() == "structured-planner"
    finally:
        os.environ.pop("OMNIROUTER_CLASSIFY_COMBO", None)

    assets = mod._image_prompt_assets()
    assert assets.get("composition_system")
    assert assets.get("composition_render_template")
    assert "weather" not in str(assets.get("composition_system")).lower()
    assert "full-bleed" in str(assets.get("composition_render_template")).lower()
    assert "no gray or blank padding" in str(assets.get("composition_render_template")).lower()

    design = mod._safe_composition_design({"placement": "left-column", "theme": "dark"})
    assert design["placement"] == "left-column"
    assert design["theme"] == "dark"
    invalid = mod._safe_composition_design({"placement": "outside", "theme": "neon"})
    assert invalid["placement"] == "auto"
    assert invalid["theme"] == "auto"

    composition = {
        "title": "Thời tiết & Giá xăng Đà Nẵng",
        "facts": [
            {"label": "Nhiệt độ", "value": "30°C", "emphasis": "primary"},
            {"label": "E5 RON 92", "value": "21.760 đ/lít", "emphasis": "important"},
        ],
        "panels": [],
        "design": {"placement": "left-column", "theme": "auto"},
        "include_timestamp": False,
    }
    prompt = mod._composition_image_prompt("Luxury Da Nang riverside at dusk", composition)
    assert "Luxury Da Nang riverside at dusk" in prompt
    assert "Thời tiết & Giá xăng Đà Nẵng" in prompt
    assert "21.760 đ/lít" in prompt
    assert '"placement":"left-column"' in prompt
    assert "Noto Sans" in prompt
    assert "bold key values" in prompt
    assert "unexplained slash pair" in prompt
    assert "/v1/overlay" not in (ZALO / "media_shortcuts.py").read_text(encoding="utf-8")
    assert not (ROOT / "architect" / "models" / "dispatcher" / "overlay.py").exists()

    print("OK composed_image_prompt_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
