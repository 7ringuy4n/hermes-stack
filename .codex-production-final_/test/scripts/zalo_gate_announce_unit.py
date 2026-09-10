#!/usr/bin/env python3
"""Unit tests for Zalo gate announce metadata (adapter)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py"


def test_gate_announce_skips_outbound_filter() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    start = source.index("async def _as_gate_announce")
    end = source.index("\n    def _as_ux_line", start)
    block = source[start:end]
    assert '"skip_outbound_filter": True' in block


def main() -> None:
    test_gate_announce_skips_outbound_filter()
    print("OK zalo_gate_announce_unit")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
