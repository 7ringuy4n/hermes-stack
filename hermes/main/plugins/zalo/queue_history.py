# -*- coding: utf-8 -*-
"""Postgres message/queue trace via zalo-api (DATABASE_URL SoT)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

log = logging.getLogger("hermes_plugins.zalo_platform.queue_history")

ENV_ENABLE = "ZALO_HISTORY_POSTGRES"


def enabled() -> bool:
    raw = (os.getenv(ENV_ENABLE) or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _api_base() -> str:
    return (os.getenv("ZALO_API_URL") or os.getenv("ADMIN_API_URL") or "http://zalo-api:8100").rstrip("/")


def _token() -> str:
    return (os.getenv("ZALO_API_TOKEN") or os.getenv("ADMIN_API_TOKEN") or "").strip()


def record(
    *,
    thread_id: str,
    event: str,
    thread_type: str = "user",
    message_id: str = "",
    role: str = "",
    content: str = "",
    task_hint: str = "",
    queue_depth: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> bool:
    if not enabled() or not str(thread_id or "").strip():
        return False
    payload = {
        "thread_id": str(thread_id),
        "thread_type": str(thread_type or "user"),
        "message_id": str(message_id or ""),
        "event": str(event),
        "role": str(role or ""),
        "content": str(content or "")[:4000],
        "task_hint": str(task_hint or ""),
        "queue_depth": queue_depth,
        "meta": meta if isinstance(meta, dict) else {},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    tok = _token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(
        _api_base() + "/v1/zalo/message-history",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        log.debug("queue_history http=%s", e.code)
        return False
    except Exception as e:  # noqa: BLE001
        log.debug("queue_history failed: %s", type(e).__name__)
        return False


def load_recent_turns(thread_id: str, thread_type: str = "user", *, limit: int = 12) -> list[dict[str, str]]:
    if not enabled() or not str(thread_id or "").strip():
        return []
    q = urllib.parse.urlencode(
        {
            "thread_id": str(thread_id),
            "thread_type": str(thread_type or "user"),
            "limit": str(limit),
        }
    )
    headers: dict[str, str] = {}
    tok = _token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(
        _api_base() + "/v1/zalo/message-history?" + q,
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            body = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception:  # noqa: BLE001
        return []
    turns = body.get("turns") if isinstance(body, dict) else None
    if not isinstance(turns, list):
        return []
    out: list[dict[str, str]] = []
    for row in turns:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "").strip().lower()
        text = str(row.get("content") or "").strip()
        if role in {"user", "assistant"} and text:
            out.append({"role": role, "content": text})
    return out
