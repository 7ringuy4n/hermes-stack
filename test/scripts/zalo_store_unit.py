# -*- coding: utf-8 -*-
"""Unit: zalo_store schema helpers without live Postgres (import + KINDS)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "zalo-api"))

import zalo_store  # noqa: E402


def main() -> int:
    assert "admin" in zalo_store.KINDS
    assert "user" in zalo_store.KINDS
    assert "dm" in zalo_store.KINDS
    assert "group" in zalo_store.KINDS
    assert "denied" in zalo_store.KINDS
    # Without DATABASE_URL, available() is False
    old = zalo_store.DSN
    zalo_store.DSN = ""
    zalo_store._pool = None
    zalo_store._ready = False
    assert zalo_store.available() is False
    zalo_store.DSN = old
    print("PASS_ZALO_STORE_UNIT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
