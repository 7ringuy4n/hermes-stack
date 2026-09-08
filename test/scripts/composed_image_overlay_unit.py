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
    _validated_evidence_queries,
    _json_object,
    _omni_overlay_plan_model,
    _omni_overlay_plan_timeout_s,
    _overlay_payload,
    _overlay_panels_payload,
    _safe_overlay_design,
    _scene_visual_prompt,
)
from overlay import apply_overlay, apply_overlay_panels  # noqa: E402
from classify_client import plan_search_queries  # noqa: E402

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
    assert assets.get("evidence_system")
    assert "weather" not in str(assets.get("composition_system")).lower()
    assert "weather" not in str(assets.get("evidence_system")).lower()
    assert _validated_evidence_queries(
        {"queries": ["current source A", "current source B", "current source A"]}
    ) == ["current source A", "current source B"]
    assert _validated_evidence_queries({"queries": ["x", "", None]}) == []

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
    invalid = _safe_overlay_design({"placement": "outside", "theme": "neon"})
    assert invalid["placement"] in {"auto", "bottom-left"}
    assert invalid["theme"] in {"auto", "dark", "light"}
    arbitrary = _safe_overlay_design(
        {
            "placement": "center-right",
            "region": {"x": 0.72, "y": 0.18, "width": 0.5, "height": 0.42},
        }
    )
    assert arbitrary["placement"] == "center-right"
    assert arbitrary["region"] == {"x": 0.72, "y": 0.18, "width": 0.28, "height": 0.42}
    bounded = _safe_overlay_design(
        {"region": {"x": 0.99, "y": 0.99, "width": 0.01, "height": 0.01}}
    )
    assert bounded["region"] == {"x": 0.82, "y": 0.72, "width": 0.18, "height": 0.28}
    assert "region" not in _safe_overlay_design({"region": {"x": "bad"}})

    lines, payload_design = _overlay_payload(parsed)
    assert lines == ["City Pulse", "Index: 92"]
    assert payload_design["line_roles"] == ["title", "primary"]

    multi = _json_object(
        '{"title":"","facts":[],"panels":['
        '{"title":"Current conditions","facts":[{"label":"Temperature","value":"30 C",'
        '"emphasis":"primary"}],"design":{"placement":"top-left"}},'
        '{"title":"Market update","facts":[{"label":"Option A","value":"20",'
        '"emphasis":"important"}],"design":{"placement":"top-right"}}],'
        '"include_timestamp":true,"timestamp_label":"Refreshed",'
        '"background_scene":"A balanced city scene"}'
    )
    panels = _overlay_panels_payload(multi)
    assert len(panels) == 2
    assert panels[0]["overlay_design"]["placement"] == "top-left"
    assert panels[1]["overlay_design"]["placement"] == "top-right"
    assert panels[0]["overlay"][0] == "Current conditions"
    assert panels[1]["overlay"][0] == "Market update"

    queries = plan_search_queries(
        {
            "instructions": [
                "Retrieve current conditions for the requested place",
                "Retrieve the latest values for the requested products",
                "RENDER: composed-image\nSCENE: balanced city scene",
            ],
            "task_details": [
                {"task_type": "search", "depends_on": []},
                {"task_type": "search", "depends_on": []},
                {"task_type": "media_generation", "depends_on": [0, 1]},
            ],
        }
    )
    assert queries == [
        "Retrieve current conditions for the requested place",
        "Retrieve the latest values for the requested products",
    ]

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
    assert "up to six" in str(assets.get("composition_system")).lower()
    assert "center-right" in str(assets.get("composition_system"))
    assert "region" in str(assets.get("composition_system"))

    from PIL import Image

    OUT.mkdir(parents=True, exist_ok=True)
    image_path = OUT / "adaptive.jpg"
    image = Image.new("RGB", (960, 540), (35, 70, 105))
    image.save(image_path, quality=90)
    apply_overlay(image_path, lines, corner="auto", design=payload_design)
    assert image_path.stat().st_size > 4000
    panel_image = OUT / "multipanel.jpg"
    image.save(panel_image, quality=90)
    rendered = apply_overlay_panels(panel_image, panels)
    assert panels[-1]["overlay"][-1].startswith("Refreshed:")
    assert rendered == 5
    assert panel_image.stat().st_size > 5000

    flexible_image = OUT / "flexible.jpg"
    Image.new("RGB", (1200, 720), (44, 78, 112)).save(flexible_image, quality=90)
    flexible_panels = [
        {
            "overlay": [f"Region {index + 1}", f"Value: {index + 10}"],
            "overlay_design": {
                "placement": "auto",
                "theme": "dark" if index % 2 == 0 else "light",
                "region": {
                    "x": (index % 3) / 3 + 0.02,
                    "y": (index // 3) / 2 + 0.03,
                    "width": 0.28,
                    "height": 0.34,
                },
            },
        }
        for index in range(6)
    ]
    assert apply_overlay_panels(flexible_image, flexible_panels) == 12
    assert flexible_image.stat().st_size > 8000

    repeated_side = OUT / "repeated-side.jpg"
    Image.new("RGB", (1200, 720), (44, 78, 112)).save(repeated_side, quality=90)
    repeated = [
        {"overlay": [f"Section {index + 1}"], "overlay_design": {"placement": "left-column"}}
        for index in range(3)
    ]
    assert apply_overlay_panels(repeated_side, repeated) == 3
    assert repeated_side.stat().st_size > 6000
    print("OK composed_image_overlay_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
