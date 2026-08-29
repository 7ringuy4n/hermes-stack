# -*- coding: utf-8 -*-
"""SOUL must clear Hermes context threat patterns + keep multi-language guidance."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOUL = (ROOT / "hermes" / "main" / "SOUL.md").read_text(encoding="utf-8")
FILLER = r"(?:[\s*_`\"'\-]){0,5}"
# Hermes tools/threat_patterns.py (context scope) — keep in sync with image.
PATTERNS = (
    ("deception_hide", rf"do\s+not\s+{FILLER}tell\s+{FILLER}the\s+user"),
    (
        "deception_hide_window",
        r"do\s+not(?:\s+\S+){0,8}\s+tell(?:\s+\S+){0,3}\s+(?:the\s+)?user",
    ),
    (
        "prompt_injection",
        rf"ignore\s+{FILLER}(previous|all|above|prior)\s+{FILLER}instructions",
    ),
    ("sys_prompt_override", r"system\s+prompt\s+override"),
    (
        "disregard_rules",
        rf"disregard\s+{FILLER}(your|all|any)\s+{FILLER}(instructions|rules|guidelines)",
    ),
    ("role_hijack", rf"you\s+are\s+{FILLER}now\s+(?:a|an|the)\s+"),
)


def main() -> int:
    for name, pat in PATTERNS:
        m = re.search(pat, SOUL, re.I)
        if m:
            line = SOUL[: m.start()].count("\n") + 1
            print(
                f"FAIL {name} still matches SOUL line {line}: {m.group(0)!r}",
                file=sys.stderr,
            )
            return 1
    if "Response language" not in SOUL and "same language" not in SOUL.lower():
        print("FAIL SOUL missing multi-language guidance", file=sys.stderr)
        return 1
    if re.search(r"(?i)only\s+support\s+vietnamese|vietnamese\s+only", SOUL):
        print("FAIL SOUL still Vietnamese-only", file=sys.stderr)
        return 1
    for needle in ("Spanish", "Japanese", "English", "same language"):
        if needle.lower() not in SOUL.lower():
            print(f"FAIL SOUL missing language example/hint: {needle}", file=sys.stderr)
            return 1
    print("OK SOUL clears Hermes threat patterns + multi-language")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
