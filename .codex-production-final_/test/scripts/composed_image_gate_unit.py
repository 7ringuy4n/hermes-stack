#!/usr/bin/env python3
"""Unit: one generic search-to-image contract owns information composition."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify_client import (  # noqa: E402
    plan_allows_search_then_composed_image,
    plan_compound_sequential,
    plan_image_render_mode,
    plan_is_search_then_image_turn,
    plan_media_shortcut_gate,
)


def main() -> int:
    composed = {
        "ok": True,
        "task_hint": "tool",
        "instructions": [
            "current public information for the requested subject",
            "RENDER: composed-image\nSCENE: editorial city illustration with calm negative space",
        ],
        "task_details": [
            {"task_type": "search", "skill": "web_search"},
            {"task_type": "media_generation", "output_type": "image"},
        ],
    }
    assert plan_image_render_mode(composed) == "composed-image"
    assert plan_allows_search_then_composed_image(composed)
    assert plan_is_search_then_image_turn(composed)
    assert plan_media_shortcut_gate(composed) == "composed_image"
    assert not plan_compound_sequential(composed)

    missing_contract = dict(composed)
    missing_contract["instructions"] = [
        composed["instructions"][0],
        "SCENE: editorial city illustration",
    ]
    assert plan_image_render_mode(missing_contract) == ""
    assert not plan_allows_search_then_composed_image(missing_contract)

    future_contract = dict(composed)
    future_contract["instructions"] = [
        composed["instructions"][0],
        "RENDER: editorial-composition\nSCENE: abstract data landscape",
    ]
    assert plan_allows_search_then_composed_image(future_contract)
    print("OK composed_image_gate_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
