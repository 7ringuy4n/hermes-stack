# -*- coding: utf-8 -*-
"""Knowledge-learn gate — no keyword dictionaries.

When secret-probe policy is classify-owned (empty markers), this returns False
so the host classify/learn-skip path owns the decision. Missing policy file
still fail-closed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


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
            or "input_block_patterns" in raw
            or "output_block_patterns" in raw
        ):
            data = raw
            break
    if data is None:
        return True
    markers = []
    for marker in data.get("input_block_patterns") or []:
        needle = str(marker or "").strip()
        if needle:
            markers.append(needle)
    if not markers:
        # Classify-owned — host must not stage; ingest does not keyword-scan.
        return False
    hay = blob.casefold()
    for needle in markers:
        if needle.casefold() in hay:
            return True
    return False
