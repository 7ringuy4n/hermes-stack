"""Drop Hermes outbound that must not reach Zalo users.

Layers (fail-closed for status frames):
1. Empty → drop
2. Deterministic Hermes *agent status frames* (progress / tool iteration / provider
   failure envelopes) — protocol shapes the gateway emits, not user NLU
3. Editable markers in ``messages/ux.json`` ``outbound_protocol_drop`` (legacy)
4. LLM ``POST /v1/outbound`` for residual lines
5. If LLM unavailable: drop status-like frames; otherwise send

Do not grow large keyword lists for natural language. Prefer skills
(``quiet-delivery``, ``zalo-channel``, ``media-out``) so Hermes does not emit
process chatter. Code only strips what the agent still leaks.
"""
from __future__ import annotations

import json
import os
import re
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

# Hermes agent status envelopes (deterministic gateway protocol shapes).
_AGENT_STATUS_RE = re.compile(
    r"(?is)^(?:"
    r"[\u23f3\u26a0\ufe0f\u2757\u23f1]|"  # hourglass / warning / heavy / stopwatch
    r"working\b|"
    r"iteration\s+\d+\s*/\s*\d+|"
    r"receiving\s+stream|"
    r"model\s+provider\s+failed|"
    r"kept\s+raw\s+provider|"
    r"check\s+gateway\s+logs|"
    r"first-time\s+tip|"
    r"interrupting\s+current\s+task|"
    r"/busy\b"
    r")"
)
_ITERATION_RE = re.compile(r"(?i)\biteration\s+\d+\s*/\s*\d+")
_WORKING_LINE_RE = re.compile(r"(?i)^\s*(?:[\u23f3\u26a0\ufe0f]+\s*)?working\b")
_PROVIDER_FAIL_RE = re.compile(
    r"(?i)model\s+provider\s+failed|raw\s+provider\s+details|check\s+gateway\s+logs\s+for\s+diagnostics"
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


def is_agent_status_frame(content: str) -> bool:
    """True for Hermes progress / tool-iteration / provider-failure envelopes."""
    t = (content or "").strip()
    if not t:
        return True
    if _ITERATION_RE.search(t):
        return True
    if _WORKING_LINE_RE.search(t):
        return True
    if _PROVIDER_FAIL_RE.search(t):
        return True
    if _AGENT_STATUS_RE.search(t) and len(t) < 400:
        return True
    return False


def is_protocol_drop(content: str) -> bool:
    """True when the line is a Hermes agent protocol status, not a user answer."""
    t = (content or "").strip()
    if not t:
        return True
    if is_agent_status_frame(t):
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
    got = classify_outbound(t)
    action = str(got.get("action") or "send").strip().lower()
    if got.get("ok") is False:
        # Fail closed for status-like residual; do not invent user-facing errors.
        return is_agent_status_frame(t) or action == "drop"
    return action == "drop"


def is_busy_interrupt_notice(content: str) -> bool:
    return drop_outbound(content)


def is_process_narration(content: str) -> bool:
    return drop_outbound(content)
