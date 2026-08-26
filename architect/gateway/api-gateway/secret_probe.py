"""Secret Probe — status independent from task_hint.

Statuses: SAFE | BLOCKED | REVIEW
Never treat SECRET as a task_hint. Do not return or log raw secrets.
Policy: config/agent/secret-probe.json (SECRET_PROBE_POLICY).
Keep in sync with hermes/main/plugins/zalo/secret_probe.py and
architect/gateway/api-gateway/secret_probe.py.

No embedded deny lists. No regex. Soft secret/env intent is owned by
classify (intent_owner=classify). Optional literal markers live in one
block_patterns list (default empty). Missing/unreadable policy when
SECRET_PROBE_POLICY is set → fail closed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

Status = Literal["SAFE", "BLOCKED", "REVIEW"]


def _policy_candidates() -> list[Path]:
    out: list[Path] = []
    env = (os.environ.get("SECRET_PROBE_POLICY") or "").strip()
    if env:
        return [Path(env)]
    out.extend(
        (
            Path("/opt/data/secret-probe.json"),
            Path("/opt/assistant/config/agent/secret-probe.json"),
            Path("/opt/stack/config/agent/secret-probe.json"),
        )
    )
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        cand = p / "config" / "agent" / "secret-probe.json"
        out.append(cand)
        if len(out) > 16:
            break
    return out


_policy: dict[str, Any] | None = None
_block_markers: list[str] = []
_policy_ok: bool = False
_classify_owned: bool = False


def _normalize_markers(items: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for x in items:
        s = str(x or "").strip()
        if s:
            out.append(s)
    return out


def _markers_from_policy(data: dict[str, Any]) -> list[str]:
    """Single block_patterns list. Legacy input/output keys merge if present."""
    primary = _normalize_markers(data.get("block_patterns"))
    if primary or "block_patterns" in data:
        return primary
    # Backward compat until all copies use block_patterns.
    merged: list[str] = []
    seen: set[str] = set()
    for key in ("input_block_patterns", "output_block_patterns"):
        for m in _normalize_markers(data.get(key)):
            k = m.casefold()
            if k in seen:
                continue
            seen.add(k)
            merged.append(m)
    return merged


def _read_policy_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if not (
        data.get("schema")
        or data.get("intent_owner") is not None
        or "block_patterns" in data
        or "input_block_patterns" in data
        or "output_block_patterns" in data
    ):
        return None
    return data


def _load_policy() -> None:
    global _policy, _block_markers, _policy_ok, _classify_owned
    if _policy is not None:
        return
    data: dict[str, Any] | None = None
    for p in _policy_candidates():
        if not p.is_file():
            continue
        loaded = _read_policy_file(p)
        if loaded is None:
            continue
        data = loaded
        break
    if data is None:
        _policy = {}
        _block_markers = []
        _policy_ok = False
        _classify_owned = False
        return
    _policy = data
    _block_markers = _markers_from_policy(data)
    owner = str(data.get("intent_owner") or "").strip().casefold()
    _classify_owned = owner in {"classify", "llm", "nlu"} or (not _block_markers)
    _policy_ok = True


def reload_policy() -> None:
    """Clear cache (tests / after admin edits)."""
    global _policy, _block_markers, _policy_ok, _classify_owned
    _policy = None
    _block_markers = []
    _policy_ok = False
    _classify_owned = False


def _marker_hit(blob: str, markers: list[str], *, casefold: bool) -> bool:
    hay = blob.casefold() if casefold else blob
    for marker in markers:
        needle = marker.casefold() if casefold else marker
        if needle and needle in hay:
            return True
    return False


def probe(text: str, *, direction: Literal["input", "output"] = "input") -> dict[str, Any]:
    """Return {status, reason}. Never includes the source text."""
    _load_policy()
    if not _policy_ok:
        return {"status": "BLOCKED", "reason": "POLICY_MISSING"}
    blob = (text or "").strip()
    if not blob:
        return {"status": "SAFE", "reason": None}
    if not _block_markers:
        return {"status": "SAFE", "reason": "CLASSIFY_OWNED" if _classify_owned else None}
    # Same marker list for input and output when using block_patterns.
    if _marker_hit(blob, _block_markers, casefold=(direction == "input")):
        return {"status": "BLOCKED", "reason": "SECRET_POLICY"}
    return {"status": "SAFE", "reason": None}


def is_blocked(text: str, *, direction: Literal["input", "output"] = "input") -> bool:
    return probe(text, direction=direction).get("status") == "BLOCKED"
