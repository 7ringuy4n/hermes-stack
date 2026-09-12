#!/usr/bin/env python3
"""Unit: security alerts remain concise and hide internal scanner envelopes."""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "architect" / "security" / "security-manager" / "app.py"
tree = ast.parse(path.read_text(encoding="utf-8"))
node = next(
    item for item in tree.body
    if isinstance(item, ast.FunctionDef) and item.name == "_risk_notice"
)
namespace = {"os": os, "re": re, "Any": Any}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)

notice = namespace["_risk_notice"](
    "eicar.com",
    {
        "archive": {"ok": True},
        "yara": {"ok": False, "reason": "yara_hit", "hits": ["eicar"]},
        "llm_judge": {"ok": True, "skipped": True, "reason": "llm_judge_disabled"},
    },
)
assert "File: eicar.com" in notice
assert "malware signature (EICAR)" in notice
assert "quarantined" in notice
assert "{" not in notice and "yara_hit" not in notice and "llm_judge" not in notice
print("OK security_alert_format_unit")
