#!/usr/bin/env python3
"""Regression checks for first-boot Hermes replica ownership."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "hermes/main/docker/hermes-replica-entry.sh"


def main() -> int:
    text = ENTRY.read_text(encoding="utf-8")
    home = 'export HERMES_HOME="${SHARED}/replicas/${RID}"'
    rehome = 'usermod -d "$HERMES_HOME" hermes'
    create = 'mkdir -p "${HERMES_HOME}"'
    checks = {
        "replica home is exported": home in text,
        "passwd home follows replica": rehome in text,
        "passwd home changes before replica creation": (
            rehome in text and create in text and text.index(rehome) < text.index(create)
        ),
        "bootstrap remains root guarded": 'if [ "$(id -u)" = "0" ]' in text,
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
