"""Secret Probe — security status independent from task_hint.

Statuses: SAFE | BLOCKED | REVIEW
Never treat SECRET as a task_hint. Do not return or log raw secrets.
Policy file: config/agent/secret-probe.json (SECRET_PROBE_POLICY).
Keep in sync with architect/security/secret-probe/probe.py.

No embedded deny lists. No regex. Markers come only from the policy file.
Missing/empty policy → fail closed (BLOCKED).
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
        # Explicit override: only this path (missing → fail closed).
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
_input_markers: list[str] = []
_output_markers: list[str] = []
_policy_ok: bool = False


def _normalize_markers(items: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for x in items:
        s = str(x or "").strip()
        if s:
            out.append(s)
    return out


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
    inputs = _normalize_markers(data.get("input_block_patterns"))
    outputs = _normalize_markers(data.get("output_block_patterns"))
    if not inputs and not outputs:
        return None
    return data


def _load_policy() -> None:
    global _policy, _input_markers, _output_markers, _policy_ok
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
        _input_markers = []
        _output_markers = []
        _policy_ok = False
        return
    _policy = data
    _input_markers = _normalize_markers(data.get("input_block_patterns"))
    _output_markers = _normalize_markers(data.get("output_block_patterns"))
    _policy_ok = bool(_input_markers or _output_markers)


def reload_policy() -> None:
    """Clear cache (tests / after admin edits)."""
    global _policy, _input_markers, _output_markers, _policy_ok
    _policy = None
    _input_markers = []
    _output_markers = []
    _policy_ok = False


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
    markers = _output_markers if direction == "output" else _input_markers
    if not markers:
        return {"status": "BLOCKED", "reason": "POLICY_MISSING"}
    if _marker_hit(blob, markers, casefold=(direction == "input")):
        return {"status": "BLOCKED", "reason": "SECRET_POLICY"}
    return {"status": "SAFE", "reason": None}


def is_blocked(text: str, *, direction: Literal["input", "output"] = "input") -> bool:
    return probe(text, direction=direction).get("status") == "BLOCKED"
