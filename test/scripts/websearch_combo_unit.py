# -*- coding: utf-8 -*-
"""Unit: web search — Omni combo web-search only."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))


def main() -> int:
    try:
        import httpx  # noqa: F401
    except ImportError:
        print("SKIP websearch_combo_unit (httpx not installed on host)")
        return 0

    os.environ["OMNIROUTER_BASE_URL"] = "http://omni-router:20129/v1"
    os.environ["OMNIROUTER_API_KEY"] = "sk-test-omni-key-for-unit"
    os.environ["MODEL_ROUTER_WEB_SEARCH_COMBO"] = "web-search"
    os.environ.pop("WEB_BACKENDS", None)
    os.environ.pop("WEB_SEARCH_COMBO_PATH", None)

    if "websearch" in sys.modules:
        del sys.modules["websearch"]
    import websearch as ws

    importlib.reload(ws)
    if "DEFAULT_CHAIN" in dir(ws):
        print("FAIL DEFAULT_CHAIN must not exist in websearch.py")
        return 1
    if hasattr(ws, "_tavily_search"):
        print("FAIL _tavily_search legacy adapter must be removed")
        return 1

    # 1) Default → omni combo only
    importlib.reload(ws)
    if ws.search_order() != ["omni"]:
        print("FAIL default order", ws.search_order())
        return 1

    health = ws.health_fields()
    if health.get("web_combo") != "web-search":
        print("FAIL combo name", health)
        return 1
    if not health.get("omni_search"):
        print("FAIL omni_search health", health)
        return 1
    if "web_combo_path" in health:
        print("FAIL legacy web_combo_path must be removed", health)
        return 1

    # 2) Without omni key → disabled
    os.environ.pop("OMNIROUTER_API_KEY", None)
    importlib.reload(ws)
    if ws.search_order():
        print("FAIL without omni key search must be empty", ws.search_order())
        return 1

    # 3) Unknown backend preference → disabled
    os.environ["OMNIROUTER_API_KEY"] = "sk-test-omni-key-for-unit"
    importlib.reload(ws)
    if ws.search_order("tavily"):
        print("FAIL direct adapter preference must be rejected", ws.search_order("tavily"))
        return 1

    # 4) Provider timeout env
    os.environ.pop("WEB_SEARCH_PROVIDER_TIMEOUT_S", None)
    importlib.reload(ws)
    if abs(ws._provider_timeout_s() - 20.0) > 0.01:
        print("FAIL default provider timeout", ws._provider_timeout_s())
        return 1
    os.environ["WEB_SEARCH_PROVIDER_TIMEOUT_S"] = "12"
    importlib.reload(ws)
    if abs(ws._provider_timeout_s() - 12.0) > 0.01:
        print("FAIL env provider timeout", ws._provider_timeout_s())
        return 1
    if ws._web_search_combo_name() != "web-search":
        print("FAIL combo env name", ws._web_search_combo_name())
        return 1
    if hasattr(ws, "_omni_search_providers"):
        print("FAIL _omni_search_providers legacy helper must be removed")
        return 1

    print("PASS websearch_combo_unit omni combo-only + timeouts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
