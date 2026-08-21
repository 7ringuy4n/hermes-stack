# -*- coding: utf-8 -*-
"""Valkey-backed short-term conversation via Session service (SESSION_URL).

sessions.json under a Hermes replica is local cache only. After recreate the
replica home is empty; hydrate from Valkey so the next turn keeps context.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

log = logging.getLogger("hermes_plugins.zalo_platform.session_memory")

ENV_ENABLE = "ZALO_SESSION_VALKEY"
DEFAULT_MAX = 12


def enabled() -> bool:
    v = (os.getenv(ENV_ENABLE) or "1").strip().lower()
    return v not in {"0", "false", "no", "off"}


def _base() -> str:
    return (os.getenv("SESSION_URL") or "http://session:8107").rstrip("/")


def session_id(thread_id: str, thread_type: str = "user") -> str:
    tid = str(thread_id or "").strip()
    tt = "group" if str(thread_type or "").lower() in {"group", "g"} else "user"
    return f"zalo:{tt}:{tid}"


def _http(method: str, path: str, payload: Optional[dict] = None, timeout: float = 2.5) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _base() + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        log.debug("session_memory %s %s http=%s", method, path, e.code)
        return {}
    except Exception as e:  # noqa: BLE001
        log.debug("session_memory %s %s failed: %s", method, path, type(e).__name__)
        return {}


def load_messages(thread_id: str, thread_type: str = "user") -> List[Dict[str, Any]]:
    if not enabled() or not str(thread_id or "").strip():
        return []
    sid = session_id(thread_id, thread_type)
    data = _http("GET", f"/v1/sessions/{sid}")
    sess = data.get("session") if isinstance(data, dict) else None
    msgs = (sess or {}).get("messages") if isinstance(sess, dict) else None
    if not isinstance(msgs, list):
        return []
    out: List[Dict[str, Any]] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip().lower()
        content = str(m.get("content") or m.get("text") or "").strip()
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content})
    return out


def hydrate_user_text(thread_id: str, thread_type: str, text: str, *, max_msgs: int = DEFAULT_MAX) -> str:
    """Prepend compact prior turns from Valkey so a new replica still has context."""
    cur = str(text or "").strip()
    if not cur:
        return text or ""
    msgs = load_messages(thread_id, thread_type)
    if not msgs:
        return cur
    try:
        cap = int(os.getenv("ZALO_SESSION_HYDRATE_MAX") or str(max_msgs))
    except ValueError:
        cap = max_msgs
    cap = max(2, min(24, cap))
    prior = msgs[-cap:]
    # Avoid double-hydrate if the adapter already injected
    if "[Prior conversation]" in cur:
        return cur
    lines = ["[Prior conversation]"]
    for m in prior:
        role = "User" if m["role"] == "user" else "Assistant"
        snippet = m["content"].replace("\n", " ").strip()
        if len(snippet) > 400:
            snippet = snippet[:400] + "…"
        lines.append(f"{role}: {snippet}")
    lines.append("[/Prior conversation]")
    lines.append("")
    lines.append(cur)
    return "\n".join(lines)


def append_turn(
    thread_id: str,
    thread_type: str,
    user_text: str,
    assistant_text: str,
) -> None:
    if not enabled() or not str(thread_id or "").strip():
        return
    user = str(user_text or "").strip()
    asst = str(assistant_text or "").strip()
    # Strip hydrate wrapper from stored user turn
    if user.startswith("[Prior conversation]"):
        parts = user.split("[/Prior conversation]", 1)
        user = parts[-1].strip() if len(parts) > 1 else user
    if not user and not asst:
        return
    sid = session_id(thread_id, thread_type)
    batch: List[Dict[str, str]] = []
    if user:
        batch.append({"role": "user", "content": user[:2000]})
    if asst:
        batch.append({"role": "assistant", "content": asst[:2000]})
    if not batch:
        return
    _http(
        "PUT",
        f"/v1/sessions/{sid}",
        {
            "session_id": sid,
            "thread_id": str(thread_id),
            "messages": batch,
            "append": True,
            "metadata": {"platform": "zalo", "thread_type": thread_type},
        },
    )
