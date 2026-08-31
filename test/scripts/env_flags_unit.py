# -*- coding: utf-8 -*-
"""Unit: env_flags active|inactive helper."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models"))

from env_flags import env_active, env_inactive, raw_env_active  # noqa: E402


def main() -> int:
    os.environ.pop("TEST_FLAG", None)
    assert env_active("TEST_FLAG", default="inactive") is False
    assert env_inactive("TEST_FLAG", default="inactive") is True
    os.environ["TEST_FLAG"] = "active"
    assert env_active("TEST_FLAG") is True
    os.environ["TEST_FLAG"] = "inactive"
    assert env_active("TEST_FLAG") is False
    os.environ["TEST_FLAG"] = "1"
    assert env_active("TEST_FLAG") is False
    assert raw_env_active(None, default="active") is True
    print("OK env_flags_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
