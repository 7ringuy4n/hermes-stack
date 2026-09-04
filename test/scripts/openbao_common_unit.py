#!/usr/bin/env python3
"""Unit: OpenBao seed merge + scrub key lists."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "main"))

from openbao_common import (  # noqa: E402
    COMPOSE_HOST_KEYS,
    ENV_SCRUB_KEYS,
    OBSOLETE_SECRET_KEYS,
    SEED_KEYS,
)


def main() -> int:
    assert "OMNIROUTER_API_KEY" in SEED_KEYS
    assert "OMNIROUTER_API_KEY" in ENV_SCRUB_KEYS
    assert "OPENBAO_DEV_ROOT_TOKEN" not in ENV_SCRUB_KEYS
    assert "OMNIROUTER_API_KEY" in COMPOSE_HOST_KEYS
    assert "POLLINATIONS_API_KEY" in SEED_KEYS
    assert "POLLINATIONS_API_KEY" in ENV_SCRUB_KEYS
    assert "POLLINATIONS_API_KEY" not in OBSOLETE_SECRET_KEYS
    assert "FAL_KEY" in OBSOLETE_SECRET_KEYS
    # Merge semantics (mirror first-setup-openbao)
    existing = {"OMNIROUTER_API_KEY": "old", "TAVILY_API_KEY": "keep"}
    incoming = {"OMNIROUTER_API_KEY": "new"}
    merged = dict(existing)
    merged.update(incoming)
    assert merged["OMNIROUTER_API_KEY"] == "new"
    assert merged["TAVILY_API_KEY"] == "keep"
    # Obsolete purge semantics
    data = {"OMNIROUTER_API_KEY": "x", "FAL_KEY": "gone"}
    for k in OBSOLETE_SECRET_KEYS:
        data.pop(k, None)
    assert "FAL_KEY" not in data
    assert data["OMNIROUTER_API_KEY"] == "x"
    print("OK openbao_common unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
