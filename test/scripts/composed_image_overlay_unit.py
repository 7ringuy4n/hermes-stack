#!/usr/bin/env python3
"""Unit: model-authored content and design are validated before adaptive rendering."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZALO = ROOT / "hermes" / "main" / "plugins" / "zalo"
DISPATCHER = ROOT / "architect" / "models" / "dispatcher"
sys.path.insert(0, str(ZALO))
sys.path.insert(0, str(DISPATCHER))

from media_shortcuts import (  # noqa: E402
    _image_prompt_assets,
    _json_object,
    _omni_overlay_plan_model,
    _omni_overlay_plan_timeout_s,
    _overlay_payload,
    _safe_overlay_design,
    _scene_visual_prompt,
)
from overlay import apply_overlay  # noqa: E402

OUT = ROOT / "scripts" / "temp" / "composed_image_overlay_unit"


def main() -> int:
    assert _omni_overlay_plan_timeout_s() == 120
    assert _omni_overlay_plan_model() == "classifier"
    os.environ["OMNIROUTER_CLASSIFY_COMBO"] = "structured-planner"
    try:
        assert _omni_overlay_plan_model() == "structured-planner"
    finally:
        os.environ.pop("OMNIROUTER_CLASSIFY_COMBO", None)
    assets = _image_prompt_assets()
    assert assets.get("composition_system")
    assert "weather" not in str(assets.get("composition_system")).lower()

    parsed = _json_object(
        'model preface {"title":"City Pulse","facts":[{"label":"Index","value":"92",'
        '"emphasis":"primary"}],"design":{"placement":"top-right","theme":"light",'
        '"font_family":"inter"},"include_timestamp":false} trailing'
    )
    design = _safe_overlay_design(parsed.get("design"))
    assert design["placement"] == "top-right"
    assert design["theme"] == "light"
    assert design["font_family"] == "inter"
    assert _safe_overlay_design({"font_family": "serif"})["font_family"] == "serif"
    invalid = _safe_overlay_design({"placement": "center", "theme": "neon"})
    assert invalid["placement"] in {"auto", "bottom-left"}
    assert invalid["theme"] in {"auto", "dark", "light"}

    lines, payload_design = _overlay_payload(parsed)
    assert lines == ["City Pulse", "Index: 92"]
    assert payload_design["line_roles"] == ["title", "primary"]

    prompt = _scene_visual_prompt(
        "Editorial watercolor skyline at dusk", composed=True
    )
    assert "watercolor" in prompt.lower()
    assert "photorealistic" not in prompt.lower()
    assert "negative space" in prompt.lower()
    assert "readable text" in prompt.lower()
    assert "background plate only" in prompt.lower()
    assert "devices" in prompt.lower()
    assert "plain gradient" in prompt.lower()
    assert "requested subject" in prompt.lower()
    assert "time-sensitive" in str(assets.get("composition_system"))
    assert "background_scene" in str(assets.get("composition_system"))

    from PIL import Image

    OUT.mkdir(parents=True, exist_ok=True)
    image_path = OUT / "adaptive.jpg"
    image = Image.new("RGB", (960, 540), (35, 70, 105))
    image.save(image_path, quality=90)
    apply_overlay(image_path, lines, corner="auto", design=payload_design)
    assert image_path.stat().st_size > 4000
    print("OK composed_image_overlay_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
