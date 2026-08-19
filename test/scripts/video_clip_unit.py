# -*- coding: utf-8 -*-
"""Unit: video clip length is caller-chosen, capped at 2 minutes."""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "dispatcher"))

from video_clip import VIDEO_SECONDS_MAX, clamp_seconds  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    if VIDEO_SECONDS_MAX != 120.0:
        print("FAIL max constant")
        return 1
    if clamp_seconds(45) != 45.0:
        print("FAIL caller 45s")
        return 1
    if clamp_seconds(200) != 120.0:
        print("FAIL cap 120")
        return 1
    if clamp_seconds(0) < 1.0:
        print("FAIL min floor")
        return 1
    os.environ["VIDEO_SECONDS_MAX"] = "30"
    try:
        if clamp_seconds(45) != 30.0:
            print("FAIL env cap")
            return 1
    finally:
        os.environ.pop("VIDEO_SECONDS_MAX", None)
    print("PASS video seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
