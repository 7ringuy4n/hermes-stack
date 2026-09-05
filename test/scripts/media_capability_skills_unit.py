#!/usr/bin/env python3
"""Unit: media combo skills and generic language/document contracts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "hermes" / "main" / "skills"


def main() -> int:
    video = (SKILLS / "video-gen" / "SKILL.md").read_text(encoding="utf-8")
    image_edit = (SKILLS / "image-edit" / "SKILL.md").read_text(encoding="utf-8")
    video_edit = (SKILLS / "video-edit" / "SKILL.md").read_text(encoding="utf-8")
    file_gen = (SKILLS / "file-gen" / "SKILL.md").read_text(encoding="utf-8")
    media = (SKILLS / "classify" / "parts" / "media.txt").read_text(encoding="utf-8")
    runtime = json.loads(
        (SKILLS / "classify" / "parts" / "image-runtime.json").read_text(encoding="utf-8")
    )

    assert "model `video-gen`" in video
    assert "480P and 3 seconds" in video
    assert "480P and 1 second" in video
    assert "model `image-edit`" in image_edit
    assert "model `video-edit`" in video_edit
    assert "Do not send it separately" in file_gen
    assert "Use one visible document title" in file_gen
    assert "Styling inside a document is not a separate image deliverable" in media
    system = runtime["composition_system"]
    assert "dominant language of the current Request message" in system
    assert "never introduce profanity" in system
    print("OK media_capability_skills_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
