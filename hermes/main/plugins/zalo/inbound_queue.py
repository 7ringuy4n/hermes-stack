"""Valkey FIFO helpers for Zalo inbound (compound parts + rate-limit defer)."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

QUEUE_ENV = "ZALO_INBOUND_QUEUE"
QUEUE_MAX_ENV = "ZALO_INBOUND_QUEUE_MAX"
QUEUE_TTL_ENV = "ZALO_INBOUND_QUEUE_TTL_S"
# A mixed media pack (txt+md+docx+xlsx+mp3+mp4+image…) arrives as one event per
# file, so the per-thread FIFO must hold a whole pack without dropping items.
DEFAULT_MAX = 16
DEFAULT_TTL = 3600
KIND_INBOUND = "inbound"
KIND_PART = "part"


def queue_flag_on() -> bool:
    raw = (os.getenv(QUEUE_ENV) or "active").strip().lower()
    return raw not in {"0", "off", "false", "no", "inactive"}


def queue_max() -> int:
    try:
        return max(1, min(100, int((os.getenv(QUEUE_MAX_ENV) or str(DEFAULT_MAX)).strip())))
    except ValueError:
        return DEFAULT_MAX


def queue_ttl_s() -> int:
    try:
        return max(60, min(86400, int((os.getenv(QUEUE_TTL_ENV) or str(DEFAULT_TTL)).strip())))
    except ValueError:
        return DEFAULT_TTL


def encode_item(item: Dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False, separators=(",", ":"))


def decode_item(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def make_item(
    *,
    kind: str,
    text: str,
    thread_id: str,
    thread_type: str,
    sender_id: str,
    sender_name: str,
    chat_type: str,
    message_id: str,
    media_urls: Optional[List[str]] = None,
    media_types: Optional[List[str]] = None,
    message_type: str = "TEXT",
    schedule_fire: bool = False,
    plan: Optional[Dict[str, Any]] = None,
    user_text: str = "",
    reply_quote: Optional[Dict[str, Any]] = None,
    explicit_quote: bool = False,
) -> Dict[str, Any]:
    return {
        "kind": kind,
        "text": text or "",
        "thread_id": str(thread_id or ""),
        "thread_type": str(thread_type or "user"),
        "sender_id": str(sender_id or ""),
        "sender_name": str(sender_name or ""),
        "chat_type": str(chat_type or "dm"),
        "message_id": str(message_id or ""),
        "media_urls": list(media_urls or []),
        "media_types": list(media_types or []),
        "message_type": str(message_type or "TEXT"),
        "schedule_fire": bool(schedule_fire),
        "plan": dict(plan) if isinstance(plan, dict) else None,
        "user_text": str(user_text or text or ""),
        "reply_quote": dict(reply_quote) if isinstance(reply_quote, dict) else None,
        "explicit_quote": bool(explicit_quote),
    }


class MemoryFifo:
    """In-process stand-in for GateStore queue (unit tests, Valkey down)."""

    def __init__(self, max_n: int = DEFAULT_MAX) -> None:
        self.max_n = max_n
        self._q: Dict[str, List[str]] = {}
        self._inflight: Dict[str, List[str]] = {}

    def queue_push(self, chat_id: str, payload: str, max_n: int, ttl_s: int) -> int:
        q = self._q.setdefault(str(chat_id), [])
        cap = max_n if max_n > 0 else self.max_n
        if len(q) >= cap:
            return -1
        q.append(payload)
        return len(q)

    def queue_push_front(self, chat_id: str, payload: str, ttl_s: int) -> None:
        q = self._q.setdefault(str(chat_id), [])
        q.insert(0, payload)

    def queue_pop(self, chat_id: str) -> Optional[str]:
        q = self._q.get(str(chat_id)) or []
        if not q:
            return None
        return q.pop(0)

    def queue_len(self, chat_id: str) -> int:
        return len(self._q.get(str(chat_id)) or [])

    def queue_active_ids(self) -> List[str]:
        """Return destinations with pending work for owner-recovery tests."""
        keys = set(self._q) | set(self._inflight)
        return sorted(
            key for key in keys if self._q.get(key) or self._inflight.get(key)
        )

    def queue_claim(self, chat_id: str) -> Optional[str]:
        key = str(chat_id)
        q = self._q.get(key) or []
        if not q:
            return None
        raw = q.pop(0)
        self._inflight.setdefault(key, []).append(raw)
        return raw

    def queue_ack(self, chat_id: str, payload: str) -> None:
        inflight = self._inflight.get(str(chat_id)) or []
        try:
            inflight.remove(payload)
        except ValueError:
            pass

    def queue_recover(self, chat_id: str) -> int:
        key = str(chat_id)
        inflight = self._inflight.get(key) or []
        if not inflight:
            return 0
        self._q.setdefault(key, [])[0:0] = inflight
        count = len(inflight)
        inflight.clear()
        return count
