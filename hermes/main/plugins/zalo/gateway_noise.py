"""Drop Hermes outbound that must not reach Zalo users.

Known Hermes agent protocol lines (413 / compaction / session reset) are
dropped from editable ``messages/ux.json`` ``outbound_protocol_drop``.
Other lines use LLM outbound classify (`action=send|drop`).
Tests inject set_outbound_planner. Empty lines are not sent.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_d = Path(__file__).resolve().parent
_shared = Path(os.getenv("HERMES_SHARED_DATA") or "/opt/data") / "plugins" / "zalo"
for _p in (_d, _shared):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

from classify_client import classify_outbound

_PROTOCOL_CACHE: list[str] | None = None
PROTOCOL_DROP_DEFAULT = (
    "Context compaction complete",
    "Request payload too large (413)",
    "Session auto-reset",
    "compression attempt",
    "vars() argument must have __dict__",
)


def _ux_path() -> Path:
    raw = (
        os.getenv("ZALO_UX_PATH")
        or os.getenv("ASSISTANT_UX_PATH")
        or ""
    ).strip()
    if raw:
        return Path(raw)
    shared = Path(os.getenv("HERMES_SHARED_DATA") or "/opt/data") / "messages" / "ux.json"
    local = _d.parents[1] / "messages" / "ux.json"
    if shared.is_file():
        return shared
    return local


def protocol_drop_markers() -> list[str]:
    global _PROTOCOL_CACHE
    if _PROTOCOL_CACHE is not None:
        return _PROTOCOL_CACHE
    markers: list[str] = []
    try:
        data = json.loads(_ux_path().read_text(encoding="utf-8"))
        raw = data.get("outbound_protocol_drop") if isinstance(data, dict) else None
        if isinstance(raw, list):
            markers = [str(x).strip() for x in raw if str(x).strip()]
    except (OSError, json.JSONDecodeError, TypeError):
        markers = []
    if not markers:
        markers = list(PROTOCOL_DROP_DEFAULT)
    _PROTOCOL_CACHE = markers
    return markers


def is_protocol_drop(content: str) -> bool:
    """True when the line is a Hermes agent protocol status, not a user answer."""
    t = (content or "").strip()
    if not t:
        return True
    for mark in protocol_drop_markers():
        if mark and mark in t:
            return True
    return False


def drop_outbound(content: str) -> bool:
    t = (content or "").strip()
    if not t:
        return True
    if is_protocol_drop(t):
        return True
    return str(classify_outbound(t).get("action") or "send").strip().lower() == "drop"


def is_busy_interrupt_notice(content: str) -> bool:
    return drop_outbound(content)


def is_process_narration(content: str) -> bool:
    return drop_outbound(content)
