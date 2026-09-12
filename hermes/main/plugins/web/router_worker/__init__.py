"""Hermes web provider backed by the stack Router Worker."""
from __future__ import annotations

from plugins.web.router_worker.provider import RouterWorkerWebSearchProvider


def register(ctx) -> None:
    """Register the provider declared by plugin.yaml with Hermes."""
    ctx.register_web_search_provider(RouterWorkerWebSearchProvider())
