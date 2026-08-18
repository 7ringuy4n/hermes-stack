# -*- coding: utf-8 -*-
"""Local unit: profile.sh defaults for routers and Grafana (no VPS)."""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "architect" / "backup-restore" / "lib" / "profile.sh"
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _default(text: str, key: str) -> str | None:
    m = re.search(rf'export {re.escape(key)}="\$\{{{re.escape(key)}:-([^}}]+)\}}"', text)
    return m.group(1) if m else None


def _case_blob(text: str, name: str) -> str:
    m = re.search(rf"\n    {re.escape(name)}\)\n(.*?)(?:\n    [a-z]+\)|\n  esac)", text, re.S)
    return m.group(1) if m else ""


def main() -> int:
    text = PROFILE.read_text(encoding="utf-8")
    fails = 0
    high = _case_blob(text, "high")
    low = _case_blob(text, "low")
    medium = _case_blob(text, "medium")
    if not high:
        print("FAIL could not isolate high) case in profile.sh")
        return 1
    profile_checks = [
        ("low", low, "ENABLE_OMNIROUTER", "1"),
        ("medium", medium, "ENABLE_OMNIROUTER", "1"),
        ("high", high, "ENABLE_OMNIROUTER", "0"),
        ("high", high, "ENABLE_MODEL_ROUTER", "1"),
        ("high", high, "ENABLE_GRAFANA", "0"),
        ("high", high, "ENABLE_PROMETHEUS", "0"),
    ]
    for profile, blob, key, want in profile_checks:
        if not blob and profile in {"low", "medium"}:
            print(f"FAIL could not isolate {profile}) case")
            fails += 1
            continue
        got = _default(blob, key)
        if got != want:
            print(f"FAIL {profile} {key} default={got!r} want={want!r}")
            fails += 1
        else:
            print(f"PASS {profile} {key} default={want}")
    if "ENABLE_9ROUTER" in text:
        print("FAIL unexpected ENABLE_9ROUTER (9router must always be on)")
        fails += 1
    else:
        print("PASS no ENABLE_9ROUTER (always-on must)")
    global_mr = _default(text, "ENABLE_MODEL_ROUTER")
    if global_mr != "1":
        print(f"FAIL global ENABLE_MODEL_ROUTER default={global_mr!r}")
        fails += 1
    else:
        print("PASS global ENABLE_MODEL_ROUTER default=1")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
