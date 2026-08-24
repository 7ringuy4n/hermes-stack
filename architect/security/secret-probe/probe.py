"""Secret Probe — security status independent from task_hint.

Statuses: SAFE | BLOCKED | REVIEW
Never treat SECRET as a task_hint. Do not return or log raw secrets.
Policy file: config/agent/secret-probe.json (SECRET_PROBE_POLICY).
Keep in sync with hermes/main/plugins/zalo/secret_probe.py.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

Status = Literal["SAFE", "BLOCKED", "REVIEW"]

_DEFAULT_INPUT = (
    "secret",
    "password",
    "passwd",
    "credentials",
    ".env",
    "env file",
    "file env",
    "environment file",
    "file môi trường",
    "file moi truong",
    "api_key",
    "private key",
    "private_key",
    "/opt/assistant",
    "/opt/data",
    "/data/assistant",
    "/etc/shadow",
    "openbao",
)
_DEFAULT_OUTPUT = (
    "sk-",
    "tvly-",
    "BEGIN PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "OPENBAO_DEV_ROOT_TOKEN",
    "HERMES_DASHBOARD_PASSWORD",
    "N9ROUTER_INITIAL_PASSWORD",
)


def _policy_candidates() -> list[Path]:
    out: list[Path] = []
    env = (os.environ.get("SECRET_PROBE_POLICY") or "").strip()
    if env:
        out.append(Path(env))
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
_input_re: re.Pattern[str] | None = None
_output_re: re.Pattern[str] | None = None


def _compile_list(items: list[str]) -> re.Pattern[str] | None:
    parts = [re.escape(str(x).strip()) for x in items if str(x).strip()]
    if not parts:
        return None
    return re.compile("|".join(parts), re.I)


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
    inputs = data.get("input_block_patterns") or []
    outputs = data.get("output_block_patterns") or []
    if not inputs and not outputs:
        return None
    return data


def _load_policy() -> dict[str, Any]:
    global _policy, _input_re, _output_re
    if _policy is not None:
        return _policy
    data: dict[str, Any] = {}
    for p in _policy_candidates():
        if not p.is_file():
            continue
        loaded = _read_policy_file(p)
        if loaded is None:
            continue
        data = loaded
        break
    if not data:
        data = {
            "schema": "assistant-secret-probe-v1",
            "input_block_patterns": list(_DEFAULT_INPUT),
            "output_block_patterns": list(_DEFAULT_OUTPUT),
        }
    _policy = data
    _input_re = _compile_list(list(data.get("input_block_patterns") or []))
    _output_re = _compile_list(list(data.get("output_block_patterns") or []))
    return data


def reload_policy() -> None:
    global _policy, _input_re, _output_re
    _policy = None
    _input_re = None
    _output_re = None


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
