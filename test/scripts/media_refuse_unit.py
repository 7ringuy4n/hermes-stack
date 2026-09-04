#!/usr/bin/env python3
"""Unit: media policy refuse gates scene/image shortcuts."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify_client import (  # noqa: E402
    plan_allows_scene_image,
    plan_is_media_policy_refuse,
    plan_media_shortcut_gate,
)


def main() -> int:
    refuse = {
        "ok": True,
        "skill": "video_gen",
        "skill_action": "refuse",
        "task_type": "media_generation",
        "output_type": "image",
        "instructions": ["SCENE: photorealistic photograph of a city"],
    }
    assert plan_is_media_policy_refuse(refuse) is True
    assert plan_allows_scene_image(refuse) is False
    assert plan_media_shortcut_gate(refuse) == "refuse"

    scenic = {
        "ok": True,
        "skill": "media_file",
        "skill_action": "generate_media",
        "task_type": "media_generation",
        "output_type": "image",
        "instructions": ["SCENE: Photorealistic photograph of Hanoi at dusk"],
    }
    assert plan_is_media_policy_refuse(scenic) is False
    assert plan_allows_scene_image(scenic) is True
    assert plan_media_shortcut_gate(scenic) == "scene_image"
    print("OK media_refuse_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
