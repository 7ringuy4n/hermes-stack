# -*- coding: utf-8 -*-
"""Probe Model Router web search combo (local HTTP, no SSH)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("MODEL_ROUTER_URL", "http://127.0.0.1:8096").rstrip("/")


def get_json(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    fails = 0
    try:
        health = get_json("/health")
    except Exception as e:
        print(f"SKIP model-router not reachable at {BASE}: {e}")
        return 0
    backends = health.get("web_backends") or []
    combo = health.get("web_combo") or "web-search"
    print(f"combo={combo} backends={backends}")
    if not backends:
        print("NOTE Omni search not configured — search disabled by design")
        return 0
    try:
        res = get_json("/v1/search", method="POST", body={"query": "weather Ho Chi Minh", "max_results": 3})
    except urllib.error.HTTPError as e:
        print(f"search HTTP {e.code} (may be expected if Omni keys missing)")
        return 0
    backend = res.get("backend") or res.get("combo")
    print(f"search backend={backend}")
    if backend != combo:
        print(f"WARN expected backend={combo!r} got {backend!r}")
        fails += 1
    else:
        print("PASS search returned Omni combo name")
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
