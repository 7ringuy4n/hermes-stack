#!/usr/bin/env python3
"""Unit: the Zalo watcher timer always gets a post-install first trigger."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    text = (ROOT / "run.sh").read_text(encoding="utf-8")
    marker = "Description=Assistant Zalo self-heal every 1 min"
    start = text.find(marker)
    if start < 0:
        print("FAIL Zalo watcher timer block missing")
        return 1
    block = text[start : start + 500]
    if "OnActiveSec=1min" not in block:
        print("FAIL watcher has no activation-relative first trigger")
        return 1
    if "OnUnitActiveSec=1min" not in block:
        print("FAIL watcher has no recurring trigger")
        return 1
    if "OnBootSec=" in block:
        print("FAIL watcher still depends on boot-relative first trigger")
        return 1
    install_block = text[start : start + 900]
    if "systemctl restart assistant-zalo-watch.timer" not in install_block:
        print("FAIL watcher install does not re-arm an already active timer")
        return 1
    print("OK Zalo watcher activation and recurrence timers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
