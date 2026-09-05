#!/usr/bin/env python3
"""Unit coverage for the transport boundary extracted from the Zalo adapter."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "hermes" / "main" / "plugins" / "zalo" / "bridge_transport.py"
SPEC = importlib.util.spec_from_file_location("zalo_bridge_transport", PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def main() -> int:
    transport = MOD.ZaloBridgeTransport("http://bridge/", "token")
    assert transport.base_url == "http://bridge"
    assert transport.headers() == {
        "Content-Type": "application/json",
        "x-bridge-token": "token",
    }
    assert transport.headers(json_content=False) == {"x-bridge-token": "token"}
    assert asyncio.run(MOD.ZaloBridgeTransport("", "").post("/send", {})) == {
        "error": "no bridge"
    }
    assert asyncio.run(transport.get(None, "/events")) == {"error": "no session"}
    print("PASS Zalo bridge transport boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
