# -*- coding: utf-8 -*-
"""Unit: web search combo — Omni-owned default + direct fallback adapters."""
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

    combo = ROOT / "architect" / "models" / "model-router" / "config" / "web-search-combo.json"
    if not combo.is_file():
        print("FAIL missing", combo)
        return 1

    os.environ["WEB_SEARCH_COMBO_PATH"] = str(combo)
    os.environ["SEARXNG_URL"] = "http://searxng:8080"
    os.environ["OMNIROUTER_BASE_URL"] = "http://omni-router:20129/v1"
    os.environ["OMNIROUTER_API_KEY"] = "sk-test-omni-key-for-unit"
    os.environ.pop("TAVILY_API_KEY", None)

    # 1) Env override wins (direct adapters)
    os.environ["WEB_BACKENDS"] = "tavily,searxng"
    if "websearch" in sys.modules:
        del sys.modules["websearch"]
    import websearch as ws

    importlib.reload(ws)
    if "DEFAULT_CHAIN" in dir(ws):
        print("FAIL DEFAULT_CHAIN must not exist in websearch.py")
        return 1
    order = ws.search_order()
    if order != ["tavily", "searxng"]:
        print("FAIL env order", order)
        return 1

    # 2) JSON file when WEB_BACKENDS unset → omni
    os.environ.pop("WEB_BACKENDS", None)
    importlib.reload(ws)
    order2 = ws.search_order()
    if order2 != ["omni"]:
        print("FAIL json order", order2)
        return 1
    health = ws.health_fields()
    if health.get("web_combo") != "websearch":
        print("FAIL combo name", health)
        return 1
    if health.get("web_backends") != ["omni"]:
        print("FAIL health backends", health)
        return 1
    if not health.get("omni_search"):
        print("FAIL omni_search health", health)
        return 1

    # 3) Explicit empty disables
    os.environ["WEB_BACKENDS"] = ""
    importlib.reload(ws)
    if ws.search_order():
        print("FAIL empty WEB_BACKENDS must disable", ws.search_order())
        return 1

    # 4) omni skipped without key
    os.environ.pop("WEB_BACKENDS", None)
    os.environ.pop("OMNIROUTER_API_KEY", None)
    importlib.reload(ws)
    if ws.search_order():
        print("FAIL omni without key must skip", ws.search_order())
        return 1

    # 5) Omni provider cascade + capped per-provider timeout
    os.environ["OMNIROUTER_API_KEY"] = "sk-test-omni-key-for-unit"
    os.environ.pop("OMNIROUTER_SEARCH_PROVIDERS", None)
    os.environ.pop("WEB_SEARCH_PROVIDER_TIMEOUT_S", None)
    importlib.reload(ws)
    providers = ws._omni_search_providers()
    if providers != ["tavily-search", "firecrawl-search", "searxng-search"]:
        print("FAIL default omni providers", providers)
        return 1
    if abs(ws._provider_timeout_s() - 20.0) > 0.01:
        print("FAIL default provider timeout", ws._provider_timeout_s())
        return 1
    os.environ["WEB_SEARCH_PROVIDER_TIMEOUT_S"] = "12"
    importlib.reload(ws)
    if abs(ws._provider_timeout_s() - 12.0) > 0.01:
        print("FAIL env provider timeout", ws._provider_timeout_s())
        return 1

    print("PASS websearch_combo_unit omni-owned + env fallback + timeouts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
