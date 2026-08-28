#!/usr/bin/env python3
"""Unit: Omni/9Router usage payload coercion for exporter metrics."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "architect" / "monitor" / "nine-exporter" / "app.py"


def _load():
    spec = importlib.util.spec_from_file_location("nine_exporter_app", APP)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["nine_exporter_app"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    mod = _load()
    history = {
        "totalRequests": 10,
        "totalPromptTokens": 100,
        "totalCompletionTokens": 20,
        "totalCost": 1.5,
        "byProvider": {"opencode-go": {"requests": 7, "cost": 1.0}},
        "byModel": {
            "opencode-go/qwen": {
                "requests": 7,
                "cost": 1.0,
                "provider": "opencode-go",
                "rawModel": "qwen",
            }
        },
    }
    got = mod._coerce_usage(history)
    assert got["totalRequests"] == 10
    assert got["byProvider"]["opencode-go"]["requests"] == 7
    assert got["byModel"]["opencode-go/qwen"]["provider"] == "opencode-go"

    analytics = {
        "summary": {
            "totalRequests": 6341,
            "promptTokens": 1000,
            "completionTokens": 200,
            "totalCost": 4.2,
        },
        "byProvider": [{"provider": "opencode-go", "requests": 1288, "cost": 0}],
        "byModel": [
            {
                "model": "hy3-free",
                "provider": "opencode",
                "rawModel": "hy3-free",
                "requests": 827,
                "cost": 0,
            }
        ],
    }
    got2 = mod._coerce_usage(analytics)
    assert got2["totalRequests"] == 6341
    assert got2["totalPromptTokens"] == 1000
    assert got2["byProvider"]["opencode-go"]["requests"] == 1288
    assert got2["byModel"]["hy3-free"]["requests"] == 827
    assert mod._coerce_usage({}) == {}
    assert mod._coerce_usage({"unrelated": 1}) == {}
    src = APP.read_text(encoding="utf-8")
    assert "/api/usage/history" in src
    assert "/api/usage/analytics" in src
    print("omni_usage_exporter_unit OK")


if __name__ == "__main__":
    main()
