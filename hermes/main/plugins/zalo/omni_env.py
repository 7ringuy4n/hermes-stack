# -*- coding: utf-8 -*-
"""Resolve OmniRouter API key/base URL for host media shortcuts (no shell probes)."""
from __future__ import annotations

import os
from pathlib import Path

_KEY_NAMES = ("OMNIROUTER_API_KEY", "OPENAI_API_KEY", "N9ROUTER_API_KEY")


def _expand_literal_newlines(text: str) -> str:
    if "\\n" in text:
        return text.replace("\\n", "\n")
    return text


def _read_env_file(path: Path) -> dict[str, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    raw = _expand_literal_newlines(raw)
    out: dict[str, str] = {}
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, val = s.split("=", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def _env_file_candidates() -> list[Path]:
    shared = (os.getenv("HERMES_SHARED_DATA") or os.getenv("HERMES_DATA_DIR") or "/opt/data").strip()
    home = (os.getenv("HERMES_HOME") or "").strip()
    roots = [
        Path(shared) / ".env",
        Path("/opt/data/.env"),
        Path("/data/assistant/.env"),
    ]
    if home:
        roots.insert(0, Path(home) / ".env")
    stack = (os.getenv("STACK_ROOT") or "/opt/assistant").strip()
    if stack:
        roots.append(Path(stack) / ".env")
    seen: set[str] = set()
    out: list[Path] = []
    for p in roots:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def resolve_omni_api_key() -> str:
    """Process env first, then shared/replica/stack .env files (no secret scan scripts)."""
    for name in _KEY_NAMES:
        val = (os.getenv(name) or "").strip()
        if val:
            return val
    for path in _env_file_candidates():
        if not path.is_file():
            continue
        data = _read_env_file(path)
        for name in _KEY_NAMES:
            val = (data.get(name) or "").strip()
            if val:
                return val
    return ""


def resolve_omni_base_url() -> str:
    val = (os.getenv("OMNIROUTER_BASE_URL") or "").strip()
    if val:
        return val.rstrip("/")
    for path in _env_file_candidates():
        if not path.is_file():
            continue
        data = _read_env_file(path)
        val = (data.get("OMNIROUTER_BASE_URL") or "").strip()
        if val:
            return val.rstrip("/")
    return "http://omni-router:20129/v1"
