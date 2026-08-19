"""Secret Probe — security status independent from task_hint.

Statuses: SAFE | BLOCKED | REVIEW
Never treat SECRET as a task_hint. Do not return or log raw secrets.
Policy file: config/agent/secret-probe.json (SECRET_PROBE_POLICY).
Keep in sync with architect/security/secret-probe/probe.py.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

Status = Literal["SAFE", "BLOCKED", "REVIEW"]


def _policy_candidates() -> list[Path]:
    out: list[Path] = []
    env = (os.environ.get("SECRET_PROBE_POLICY") or "").strip()
    if env:
        out.append(Path(env))
    out.extend(
        (
            Path("/opt/data/secret-probe.json"),
            Path("/opt/assistant/config/agent/secret-probe.json"),
        )
    )
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        cand = p / "config" / "agent" / "secret-probe.json"
        out.append(cand)
        if len(out) > 12:
            break
    return out


_policy: dict[str, Any] | None = None
_input_re: re.Pattern[str] | None = None
_output_re: re.Pattern[str] | None = None


def _compile_list(items: list[str]) -> re.Pattern[str] | None:
    parts = [re.escape(str(x).strip()) for x in items if str(x).strip()]
    if not parts:
        return None
    return re.compile("|".join(parts), re.I)


def _load_policy() -> dict[str, Any]:
    global _policy, _input_re, _output_re
    if _policy is not None:
        return _policy
    data: dict[str, Any] = {}
    for p in _policy_candidates():
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            break
        except (OSError, json.JSONDecodeError):
            continue
    _policy = data
    _input_re = _compile_list(list(data.get("input_block_patterns") or []))
    _output_re = _compile_list(list(data.get("output_block_patterns") or []))
    return data


def probe(text: str, *, direction: Literal["input", "output"] = "input") -> dict[str, Any]:
    """Return {status, reason}. Never includes the source text."""
    _load_policy()
    blob = (text or "").strip()
    if not blob:
        return {"status": "SAFE", "reason": None}
    pat = _output_re if direction == "output" else _input_re
    if pat is None:
        return {"status": "SAFE", "reason": None}
    if pat.search(blob.lower() if direction == "input" else blob):
        return {"status": "BLOCKED", "reason": "SECRET_POLICY"}
    return {"status": "SAFE", "reason": None}


def is_blocked(text: str, *, direction: Literal["input", "output"] = "input") -> bool:
    return probe(text, direction=direction).get("status") == "BLOCKED"
