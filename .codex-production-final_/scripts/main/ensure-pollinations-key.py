#!/usr/bin/env python3
"""Ensure POLLINATIONS_API_KEY for Omni image-capable Pollinations members.

Usage (interactive device-flow):
  python3 scripts/main/ensure-pollinations-key.py

Non-interactive: set POLLINATIONS_API_KEY in OpenBao / .env beforehand.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

path = Path(__file__).resolve().parent / "first-setup-omnirouter.py"
spec = importlib.util.spec_from_file_location("first_setup_omnirouter", path)
if spec is None or spec.loader is None:
    raise SystemExit(f"cannot load {path}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
os.environ.setdefault("POLLINATIONS_DEVICE_FLOW", "1")
env = mod.load_env(mod.ROOT / ".env")
key = mod.ensure_pollinations_api_key(env, interactive=True)
if not key:
    raise SystemExit(1)
print("OK: Pollinations key ready for Omni provider registration")
raise SystemExit(0)
