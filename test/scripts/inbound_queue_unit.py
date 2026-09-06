# -*- coding: utf-8 -*-
"""Unit tests for Valkey inbound FIFO helpers (no VPS, no Valkey)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))
sys.path.insert(0, str(ROOT / "test" / "scripts"))

from inbound_queue import (  # noqa: E402
    DEFAULT_MAX,
    KIND_INBOUND,
    MemoryFifo,
    decode_item,
    encode_item,
    make_item,
    queue_max,
)
from multi_request import split_compound_requests  # noqa: E402
from classify_fixtures import (  # noqa: E402
    FIXTURE_QUEUE_NOW as PLENTY_NOW,
    FIXTURE_QUEUE_SCHEDULE as PLENTY_SCHEDULE,
    install_unit_planner,
)

install_unit_planner()

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    # Cap must fit a whole mixed media pack (one inbound event per file).
    if DEFAULT_MAX < 16 or queue_max() != DEFAULT_MAX:
        print(f"FAIL default cap {DEFAULT_MAX} queue_max={queue_max()} want >=16")
        return 1
    fifo = MemoryFifo(max_n=3)
    items = []
    for i, text in enumerate(split_compound_requests(PLENTY_NOW), start=1):
        items.append(
            make_item(
                kind=KIND_INBOUND if i == 1 else "part",
                text=text,
                thread_id="t1",
                thread_type="user",
                sender_id="u1",
                sender_name="u",
                chat_type="dm",
                message_id=f"m{i}",
            )
        )
        n = fifo.queue_push("t1", encode_item(items[-1]), 3, 3600)
        if n != i:
            print(f"FAIL push len {n} != {i}")
            return 1
    if fifo.queue_push("t1", encode_item(items[0]), 3, 3600) != -1:
        print("FAIL cap should be -1")
        return 1
    popped = []
    while True:
        raw = fifo.queue_pop("t1")
        if not raw:
            break
        got = decode_item(raw)
        if not got:
            print("FAIL decode")
            return 1
        popped.append(got["text"])
    if len(popped) != 3:
        print(f"FAIL pop count {popped!r}")
        return 1
    if "Chào" not in popped[0] or "hình" not in popped[1] or "xăng" not in popped[2]:
        print(f"FAIL FIFO order {popped!r}")
        return 1
    print("PASS FIFO 3 immediate parts + cap")

    # A claimed turn survives an owner crash and is restored ahead of later
    # work. Independent DM/group destinations remain separately discoverable.
    reliable = MemoryFifo(max_n=4)
    reliable.queue_push("dm-1", "first", 4, 3600)
    reliable.queue_push("dm-1", "second", 4, 3600)
    reliable.queue_push("group-1", "group", 4, 3600)
    if reliable.queue_active_ids() != ["dm-1", "group-1"]:
        print(f"FAIL active queue registry {reliable.queue_active_ids()!r}")
        return 1
    claimed = reliable.queue_claim("dm-1")
    if claimed != "first" or reliable.queue_recover("dm-1") != 1:
        print("FAIL abandoned claim recovery")
        return 1
    replay = reliable.queue_claim("dm-1")
    if replay != "first":
        print(f"FAIL recovered ordering {replay!r}")
        return 1
    reliable.queue_ack("dm-1", replay)
    if reliable.queue_claim("group-1") != "group":
        print("FAIL group queue independence")
        return 1
    print("PASS durable claim recovery + independent destinations")

    kept = split_compound_requests(PLENTY_SCHEDULE)
    if len(kept) != 1 or "E10 RON95" not in kept[0]:
        print(f"FAIL daily plenty list must stay one job, got {kept!r}")
        return 1
    now = split_compound_requests(PLENTY_NOW)
    if len(now) != 3:
        print(f"FAIL immediate plenty expected 3, got {now!r}")
        return 1
    print("PASS plenty schedule stays one job; immediate splits to 3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
