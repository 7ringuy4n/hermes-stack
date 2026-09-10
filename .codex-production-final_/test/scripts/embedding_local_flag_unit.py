#!/usr/bin/env python3
"""Unit: Compose-style boolean values enable the local embedding fallback."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "architect" / "tools" / "embedding" / "app.py"


def load_with(value: str):
    os.environ["EMBED_LOCAL_FALLBACK"] = value
    spec = importlib.util.spec_from_file_location(f"embedding_app_{value}", APP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    for value in ("1", "true", "yes", "on", "active"):
        assert load_with(value).LOCAL_FALLBACK is True
    for value in ("0", "false", "off", "disabled"):
        assert load_with(value).LOCAL_FALLBACK is False
    print("OK local embedding fallback flags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
