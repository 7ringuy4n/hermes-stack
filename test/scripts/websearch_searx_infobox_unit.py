#!/usr/bin/env python3
"""Unit: SearXNG infoboxes remain usable when engines return no result rows."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "architect" / "models" / "model-router" / "websearch.py"


class Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "results": [],
            "infoboxes": [
                {
                    "title": "OpenBao",
                    "content": "OpenBao is an open source secrets manager.",
                    "urls": [{"title": "OpenBao", "url": "https://openbao.org/"}],
                }
            ],
        }


class Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def get(self, *_args, **_kwargs) -> Response:
        return Response()


def main() -> int:
    spec = importlib.util.spec_from_file_location("websearch_infobox_unit", APP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._searxng_url = lambda: "http://searxng:8080"
    module.httpx.AsyncClient = lambda **_kwargs: Client()
    result = asyncio.run(module._searxng_search("OpenBao", 3))
    assert result["backend"] == "searxng"
    assert result["results"][0]["title"] == "OpenBao"
    assert result["results"][0]["url"] == "https://openbao.org/"
    print("OK SearXNG infobox fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
