# -*- coding: utf-8 -*-
"""Dispatcher HTTP for a single classified office-file job.

Intent lives in classify JSON. This module does not phrase-scan user prose.
The adapter calls run_office_create only when plan_allows_office_shortcut is true.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

log = logging.getLogger("hermes_plugins.zalo_platform.media_shortcuts")


def dispatcher_url() -> str:
    return (os.getenv("DISPATCHER_URL") or "http://dispatcher:8090").rstrip("/")


def _post(path: str, body: dict, timeout: float = 60.0) -> Dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        dispatcher_url() + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def run_office_create(
    text: str,
    thread_id: str,
    thread_type: str = "user",
    *,
    classified: bool = False,
) -> Optional[dict]:
    """POST /v1/office-file. Caller must already have a single file-create plan."""
    if not classified:
        return None
    prompt = (text or "").strip()
    if not prompt:
        return None
    try:
        out = _post(
            "/v1/office-file",
            {
                "prompt": prompt,
                "thread_id": str(thread_id),
                "thread_type": "group" if str(thread_type).lower() in {"group", "g"} else "user",
                "caption": "",
            },
            timeout=45.0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("office shortcut failed: %s", type(e).__name__)
        return None
    if isinstance(out, dict) and out.get("ok"):
        return out
    return None


def run_text_poster(
    text: str,
    thread_id: str = "",
    thread_type: str = "user",
    *,
    classified: bool = False,
) -> Optional[dict]:
    """POST /v1/image text-poster. Caller must already have a media_generation plan."""
    del thread_id, thread_type
    if not classified:
        return None
    prompt = (text or "").strip()
    if not prompt:
        return None
    try:
        out = _post(
            "/v1/image",
            {
                "prompt": prompt,
                "filename": "poster.png",
                "refine": False,
                "mode": "text-poster",
            },
            timeout=60.0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("text-poster shortcut failed: %s", type(e).__name__)
        return None
    if isinstance(out, dict) and out.get("ok"):
        return out
    return None
