# -*- coding: utf-8 -*-
"""Unit: Router Worker web search combo order (Tavily -> SearXNG)."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))


def main() -> int:
    os.environ["WEB_BACKENDS"] = "tavily,searxng"
    os.environ["SEARXNG_URL"] = "http://searxng:8080"
    os.environ.pop("TAVILY_API_KEY", None)
    if "websearch" in sys.modules:
        del sys.modules["websearch"]
    import websearch as ws

    importlib.reload(ws)
    order = ws.search_order()
    if order != ["tavily", "searxng"]:
        print("FAIL order", order)
        return 1
    forced = ws.search_order("searxng")
    if forced[0] != "searxng" or "tavily" not in forced:
        print("FAIL preferred", forced)
        return 1
    health = ws.health_fields()
    if health.get("searxng") is not True:
        print("FAIL health", health)
        return 1
    if health.get("web_keys", {}).get("tavily") is not False:
        print("FAIL empty tavily key should be false", health)
        return 1
    print("PASS websearch_combo_unit", order)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
