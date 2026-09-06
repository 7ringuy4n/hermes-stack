#!/usr/bin/env python3
"""Contract check for acknowledgement-backed Zalo delivery history."""
from __future__ import annotations

import ast
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    source = (root / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(encoding="utf-8")
    ast.parse(source)
    error_guard = source.index('if res.get("error"):\n                return SendResult(success=False')
    delivery = source.index('event="delivered"', error_guard)
    success = source.index('return SendResult(success=True, message_id=msg_id)', delivery)
    assert error_guard < delivery < success
    assert 'meta={"quoted": bool(used_quote)}' in source[delivery:success]
    print("zalo_delivery_history_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
