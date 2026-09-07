#!/usr/bin/env python3
"""Unit coverage for structurally safe Zalo group-member snapshots."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "zalo-api"))

from group_members import complete_group_members  # noqa: E402


def main() -> int:
    thread = "900000000000000001"
    versioned = {
        "gridInfoMap": {
            thread: {
                "totalMember": 3,
                "memVerList": [
                    "800000000000000001_1",
                    "800000000000000002_4",
                    "800000000000000003_2",
                ],
                "creatorId": "800000000000000001",
                "adminIds": ["800000000000000002"],
            }
        }
    }
    got = complete_group_members(versioned, thread)
    assert got is not None and len(got) == 3
    assert [row["role"] for row in got] == ["owner", "admin", "member"]
    assert got[1]["raw_metadata"] == {"version": "4"}

    direct = {
        "totalMember": "2",
        "memberIds": [
            {"userId": "700000000000000001", "source": "bridge"},
            "700000000000000002",
        ],
    }
    got = complete_group_members(direct, thread)
    assert got is not None and len(got) == 2
    assert got[0]["raw_metadata"] == {"source": "bridge"}

    assert complete_group_members(
        {"totalMember": 3, "memVerList": ["1_1", "2_1"]}, thread
    ) is None
    assert complete_group_members(
        {"totalMember": 1, "memVerList": ["invalid"], "hasMoreMember": False}, thread
    ) is None
    assert complete_group_members(
        {"totalMember": 1, "memberIds": ["3"], "hasMoreMember": True}, thread
    ) is None
    print("PASS_ZALO_GROUP_MEMBERS_UNIT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
