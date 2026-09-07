"""Privacy-preserving provider session correlation."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Mapping


HEADER_NAME = "x-opencode-session"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_user_content(body: Mapping[str, Any]) -> str:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in messages:
        if not isinstance(message, dict) or _text(message.get("role")).lower() != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return ""


def _request_content(body: Mapping[str, Any]) -> str:
    """Return a stable stateless-request discriminator when no chat id exists."""
    for key in ("text", "prompt", "input"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value.strip()}"
        if isinstance(value, (dict, list)) and value:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            return f"{key}:{encoded}"
    return ""


def conversation_seed(headers: Mapping[str, Any], body: Mapping[str, Any]) -> str:
    """Return the best stable conversation discriminator available to the proxy."""
    for key in (HEADER_NAME, "x-conversation-id", "x-session-id"):
        value = _text(headers.get(key))
        if value:
            return f"header:{key}:{value}"
    metadata = body.get("metadata")
    meta = metadata if isinstance(metadata, dict) else {}
    for key in ("conversation_id", "session_id", "thread_id", "chat_id"):
        value = _text(body.get(key) or meta.get(key))
        if value:
            return f"body:{key}:{value}"
    user = _text(body.get("user"))
    if user:
        return f"user:{user}"
    first_user = _first_user_content(body)
    if first_user:
        return f"first-user:{first_user}"
    request_content = _request_content(body)
    if request_content:
        return f"request:{request_content}"
    return "anonymous"


def opencode_session(headers: Mapping[str, Any], body: Mapping[str, Any]) -> str:
    """Create an opaque stable identifier without forwarding a raw chat identifier."""
    namespace = _text(os.environ.get("OPENCODE_SESSION_NAMESPACE")) or "router-worker"
    seed = conversation_seed(headers, body)
    digest = hashlib.sha256(f"{namespace}\0{seed}".encode("utf-8")).hexdigest()
    return f"ocg-{digest[:40]}"


def with_opencode_session(
    headers: Mapping[str, str], session: str
) -> dict[str, str]:
    out = dict(headers)
    if _text(session):
        out[HEADER_NAME] = _text(session)
    return out
