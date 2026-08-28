#!/usr/bin/env python3
"""Unit: outbound privacy uses map + optional text; adapter drops identity regex."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZALO = ROOT / "hermes" / "main" / "plugins" / "zalo"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    adapter_src = (ZALO / "adapter.py").read_text(encoding="utf-8")
    assert "this is a dm with" not in adapter_src
    assert "trong\\s+thư" not in adapter_src
    assert "Never leak chat/thread" not in adapter_src
    assert "Chat/thread/DM/folder meta scrubbing is owned by classify" in adapter_src

    cc = _load("classify_client_ut", ZALO / "classify_client.py")
    got = cc.normalize_outbound({"action": "SEND", "text": "Hello"})
    assert got["ok"] is True and got["action"] == "send" and got["text"] == "Hello"
    got2 = cc.normalize_outbound({"action": "weird"})
    assert got2["action"] == "send" and "text" not in got2
    got3 = cc.normalize_outbound({"action": "drop"})
    assert got3["action"] == "drop"
    assert cc.OUTBOUND_ACTION_MAP["drop"] == "drop"

    core = (ROOT / "hermes" / "main" / "skills" / "classify" / "parts" / "core.txt").read_text(encoding="utf-8")
    assert "PRIVACY IN FIELDS" in core
    ob = (ROOT / "hermes" / "main" / "skills" / "outbound" / "outbound.json").read_text(encoding="utf-8")
    assert "chat/thread" in ob.lower() or "thread" in ob.lower()
    print("outbound_privacy_unit OK")


if __name__ == "__main__":
    main()
