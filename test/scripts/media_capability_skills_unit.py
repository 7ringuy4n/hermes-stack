#!/usr/bin/env python3
"""Unit: media combo skills and generic language/document contracts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "hermes" / "main" / "skills"


def main() -> int:
    image_edit = (SKILLS / "image-edit" / "SKILL.md").read_text(encoding="utf-8")
    file_gen = (SKILLS / "file-gen" / "SKILL.md").read_text(encoding="utf-8")
    media = (SKILLS / "classify" / "parts" / "media.txt").read_text(encoding="utf-8")
    runtime = json.loads(
        (SKILLS / "classify" / "parts" / "image-runtime.json").read_text(encoding="utf-8")
    )

    assert "model `image-edit`" in image_edit
    assert not (SKILLS / ("video" + "-gen")).exists()
    assert not (SKILLS / ("video" + "-edit")).exists()
    assert "Do not send it separately" in file_gen
    assert "Use one visible document title" in file_gen
    assert "verify that locality labels" in file_gen
    assert "dominant language of the current user message" in file_gen
    assert "every visible word" in file_gen
    assert "Do not add bilingual translations" in file_gen
    assert "do not merge conflicting values" in file_gen
    assert "requested time and subject scope is a hard boundary" in file_gen
    assert "forecast tables" in file_gen and "are prohibited" in file_gen
    assert "Do not invent causal explanations" in file_gen
    assert "Before the final office-file call, self-review" in file_gen
    assert "Keep a compact snapshot on one page" in file_gen
    assert "never apply a timezone offset twice" in file_gen
    assert "supposedly current observation that is in the future" in file_gen
    assert "measurement units customary for that language/locale" in file_gen
    assert "do not leave a large unused lower area" in file_gen
    assert "Styling inside a document is not a separate image deliverable" in media
    system = runtime["composition_system"]
    assert "dominant language of the current Request message" in system
    assert "never introduce profanity" in system
    print("OK media_capability_skills_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
