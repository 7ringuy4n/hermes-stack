# -*- coding: utf-8 -*-
"""Knowledge-learn gate — no keyword dictionaries.

Uses policy block_patterns (default empty). When empty / classify-owned,
returns False so host classify/learn-skip owns the decision. Missing policy
file still fail-closed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _markers_from_policy(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    keys = ("block_patterns",)
    if "block_patterns" not in data:
        keys = ("input_block_patterns", "output_block_patterns")
    for key in keys:
        for marker in data.get(key) or []:
            needle = str(marker or "").strip()
            if not needle:
                continue
            k = needle.casefold()
            if k in seen:
                continue
            seen.add(k)
            out.append(needle)
    return out


def secret_probe_blocked(text: str) -> bool:
    blob = (text or "").strip()
    if not blob:
        return False
    candidates: list[Path] = []
    env = (os.environ.get("SECRET_PROBE_POLICY") or "").strip()
    if env:
        candidates = [Path(env)]
    else:
        candidates = [
            Path("/opt/data/secret-probe.json"),
            Path("/data/assistant/secret-probe.json"),
            Path("/opt/assistant/config/agent/secret-probe.json"),
            Path(__file__).resolve().parents[3] / "config" / "agent" / "secret-probe.json",
        ]
    data: dict[str, Any] | None = None
    for path in candidates:
        try:
            if not path.is_file():
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(raw, dict) and (
            raw.get("schema")
            or raw.get("intent_owner") is not None
            or "block_patterns" in raw
            or "input_block_patterns" in raw
            or "output_block_patterns" in raw
        ):
            data = raw
            break
    if data is None:
        return True
    markers = _markers_from_policy(data)
    if not markers:
        return False
    hay = blob.casefold()
    for needle in markers:
        if needle.casefold() in hay:
            return True
    return False
