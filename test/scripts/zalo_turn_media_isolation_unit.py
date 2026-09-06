"""Regression: late media from one turn cannot mute the next Zalo turn."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from autosend import begin_turn_state, mark_media_sent, media_sent_in_turn  # noqa: E402


def main() -> int:
    tokens: dict[str, int] = {}
    clocks: dict[str, dict[str, float]] = {}
    sent: dict[str, int] = {}

    first = begin_turn_state(tokens, clocks, sent, "thread-a", 100.0)
    assert first == 1
    assert clocks["thread-a"]["t0"] == 100.0
    mark_media_sent(sent, "thread-a", first)
    assert media_sent_in_turn(sent, "thread-a", tokens["thread-a"]) is True

    second = begin_turn_state(tokens, clocks, sent, "thread-a", 200.0)
    assert second == 2
    assert media_sent_in_turn(sent, "thread-a", tokens["thread-a"]) is False

    # A sender that started in the previous turn may finish after turn two
    # begins. Recording its captured token must not contaminate turn two.
    mark_media_sent(sent, "thread-a", first)
    assert media_sent_in_turn(sent, "thread-a", tokens["thread-a"]) is False
    mark_media_sent(sent, "thread-a", second)
    assert media_sent_in_turn(sent, "thread-a", tokens["thread-a"]) is True

    third = begin_turn_state(tokens, clocks, sent, "thread-b", 300.0)
    assert third == 1
    assert media_sent_in_turn(sent, "thread-a", tokens["thread-a"]) is True
    assert media_sent_in_turn(sent, "thread-b", tokens["thread-b"]) is False
    print("PASS_ZALO_TURN_MEDIA_ISOLATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
