#!/usr/bin/env python3
"""Unit: channel name from classify plan and normalized resolve."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))
sys.path.insert(0, str(ROOT / "architect" / "zalo-api"))

from channels_client import (  # noqa: E402
    apply_schedule_delivery_target,
    extract_target_group_ref,
)
import channels_registry as reg  # noqa: E402


def test_extract() -> None:
    # Host no longer phrase-scans; destination must come from classify JSON.
    assert (
        extract_target_group_ref(
            "schedule daily at 07:00 to group Family with a greeting",
            {},
        )
        == ""
    )
    assert (
        extract_target_group_ref(
            "schedule daily at 07:00 to group Ops hello",
            {"target_channel": "Ops"},
        )
        == "Ops"
    )
    assert (
        extract_target_group_ref(
            "ignored",
            {"target_channel": "Zalo LC group"},
        )
        == "LC group"
    )
    assert (
        extract_target_group_ref(
            "hello",
            {"target_channel": "LC group"},
        )
        == "LC group"
    )
    assert extract_target_group_ref("hello", {}) == ""


def test_resolve_prefixed_and_reverse(tmp_path: Path) -> None:
    reg.REGISTRY_FILE = tmp_path / "registry.json"
    reg.upsert("zalo", "12345", name="Lab group", kind="group")
    hit = reg.resolve("zalo", "Zalo LC group")
    assert hit is None
    hit = reg.resolve("zalo", "Zalo Lab group")
    assert hit and hit["external_id"] == "12345"
    hit2 = reg.resolve("zalo", "Lab group")
    assert hit2 and hit2["external_id"] == "12345"


def test_resolve_and_apply(tmp_path: Path) -> None:
    reg.REGISTRY_FILE = tmp_path / "registry.json"
    reg.upsert("zalo", "111", name="Café Team", kind="group")
    reg.upsert("zalo", "999", name="Tn", kind="user")
    hit = reg.resolve("zalo", "cafe team")
    assert hit and hit["external_id"] == "111"
    origin = {
        "platform": "zalo",
        "chat_id": "999",
        "thread_id": "999",
        "user_id": "999",
        "chat_name": "Tn",
    }
    context = {
        "thread_id": "999",
        "thread_type": "user",
        "chat_type": "dm",
        "sender_id": "999",
        "sender_name": "Tn",
        "execute": "hermes",
    }

    import channels_client as cc

    def _fake_resolve(ref: str, *, platform: str = "zalo"):
        return reg.resolve(platform, ref)

    cc.resolve_channel = _fake_resolve  # type: ignore
    new_o, new_c, note = apply_schedule_delivery_target(
        text="schedule at 07:00 and send a greeting to Cafe Team",
        plan={"target_channel": "Cafe Team"},
        origin=origin,
        context=context,
        current_thread_type="user",
    )
    assert note and note.startswith("deliver_to:")
    assert new_o["thread_id"] == "111"
    assert new_c["thread_type"] == "group"
    assert new_o["user_id"] == "999"


def main() -> int:
    test_extract()
    with tempfile.TemporaryDirectory() as td:
        test_resolve_prefixed_and_reverse(Path(td))
        test_resolve_and_apply(Path(td))
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
