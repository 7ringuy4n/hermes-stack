# -*- coding: utf-8 -*-
"""Verify rewritten SOUL.md does not trip deception_hide."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOUL = (ROOT / "hermes" / "main" / "SOUL.md").read_text(encoding="utf-8")
FILLER = r"(?:[\s*_`\"'\-]){0,5}"
PAT = re.compile(rf"do\s+not\s+{FILLER}tell\s+{FILLER}the\s+user", re.I)


def main() -> int:
    if PAT.search(SOUL) or re.search(r"do\s+not\s+tell\s+the\s+user", SOUL, re.I):
        print("FAIL deception_hide still matches SOUL", file=sys.stderr)
        return 1
    print("OK SOUL clears deception_hide pattern")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
