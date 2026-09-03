#!/usr/bin/env python3
"""Repair/sync OmniRouter combos, providers, and media wiring.

Use after catalog changes, custom image providers, or combo drift.
Does NOT mint a new API key when OMNIROUTER_API_KEY is already set.

  bash run.sh update-omnirouter
  python3 scripts/main/update-omnirouter.py
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "scripts" / "main" / "first-setup-omnirouter.py"

if __name__ == "__main__":
    sys.argv = [str(TARGET), "--update"]
    runpy.run_path(str(TARGET), run_name="__main__")
