# -*- coding: utf-8 -*-
"""Unit: host must send classify refuse without Hermes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify_client import plan_is_host_direct_reply  # noqa: E402


def main() -> int:
    refuse = {
        "ok": True,
        "task_hint": "normal",
        "process_original_message": False,
        "skill": None,
        "message": "Cannot provide secrets, credentials, or protected server paths.",
        "instructions": ["Cannot provide secrets, credentials, or protected server paths."],
    }
    assert plan_is_host_direct_reply(refuse) is True
    hello = {
        "ok": True,
        "task_hint": "normal",
        "process_original_message": True,
        "skill": None,
        "message": "hi",
        "instructions": ["hi"],
    }
    assert plan_is_host_direct_reply(hello) is False
    schedule = {
        "ok": True,
        "task_hint": "schedule",
        "process_original_message": False,
        "skill": "schedule",
        "message": "nhắc uống nước",
        "instructions": ["nhắc uống nước"],
    }
    assert plan_is_host_direct_reply(schedule) is False
    deliver = {
        "ok": True,
        "task_hint": "normal",
        "process_original_message": False,
        "skill": None,
        "skill_action": "deliver",
        "message": "hello group",
        "instructions": ["hello group"],
    }
    assert plan_is_host_direct_reply(deliver) is False
    print("host_direct_reply_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
