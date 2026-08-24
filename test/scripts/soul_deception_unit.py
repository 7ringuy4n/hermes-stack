# -*- coding: utf-8 -*-
"""Strengthen SOUL checks: deception_hide + multi-language section present."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOUL = (ROOT / "hermes" / "main" / "SOUL.md").read_text(encoding="utf-8")
FILLER = r"(?:[\s*_`\"'\-]){0,5}"
PAT = re.compile(rf"do\s+not\s+{FILLER}tell\s+{FILLER}the\s+user", re.I)
# Hermes prompt_builder: do not … tell … (the) user with up to 8 words between.
WINDOW = re.compile(
    r"do\s+not(?:\s+\S+){0,8}\s+tell(?:\s+\S+){0,3}\s+(?:the\s+)?user",
    re.I,
)


def main() -> int:
    if PAT.search(SOUL) or WINDOW.search(SOUL) or re.search(r"do\s+not\s+tell\s+the\s+user", SOUL, re.I):
        print("FAIL deception_hide still matches SOUL", file=sys.stderr)
        return 1
    if "Response language" not in SOUL and "same language" not in SOUL.lower():
        print("FAIL SOUL missing multi-language guidance", file=sys.stderr)
        return 1
    # Must not imply Vietnamese-only
    if re.search(r"(?i)only\s+support\s+vietnamese|vietnamese\s+only", SOUL):
        print("FAIL SOUL still Vietnamese-only", file=sys.stderr)
        return 1
    for needle in ("Spanish", "Japanese", "English", "same language"):
        if needle.lower() not in SOUL.lower():
            print(f"FAIL SOUL missing language example/hint: {needle}", file=sys.stderr)
            return 1
    print("OK SOUL clears deception_hide + multi-language")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
