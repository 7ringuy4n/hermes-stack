# -*- coding: utf-8 -*-
"""Unit tests for Valkey inbound FIFO helpers (no VPS, no Valkey)."""
from __future__ import annotations

import io
import asyncio
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
from multi_request import parts_from_plan, split_compound_requests  # noqa: E402
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
                user_text=f"user-{i}",
                reply_quote={"msgId": f"q{i}", "content": f"quote-{i}"},
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
        expected_index = len(popped)
        if got.get("user_text") != f"user-{expected_index}":
            print("FAIL queued user text correlation")
            return 1
        quote = got.get("reply_quote") or {}
        if quote.get("msgId") != f"q{expected_index}":
            print("FAIL queued quote correlation")
            return 1
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

    # Several execution nodes may be one deliverable. A dependency edge makes
    # the graph atomic; only independent roots become queue parts.
    atomic = parts_from_plan(
        "Create one grounded visual",
        {
            "task_hint": "normal",
            "instructions": ["Retrieve current facts", "Render one visual"],
            "task_details": [
                {"task_type": "search", "depends_on": []},
                {"task_type": "media_generation", "depends_on": [0]},
            ],
        },
    )
    if atomic != ["Create one grounded visual"]:
        print(f"FAIL dependency graph split into queue parts {atomic!r}")
        return 1
    independent = parts_from_plan(
        "Do two separate jobs",
        {
            "task_hint": "tool",
            "instructions": ["First job", "Second job"],
            "task_details": [
                {"task_type": "chat", "depends_on": []},
                {"task_type": "search", "depends_on": []},
            ],
        },
    )
    if independent != ["First job", "Second job"]:
        print(f"FAIL independent jobs did not split {independent!r}")
        return 1
    print("PASS dependent graph atomic + independent roots split")

    # The gateway completion guard is conversation-scoped. The same
    # destination must remain serialized, while an unrelated DM and group must
    # not wait behind one owner-wide lock.
    adapter_source = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    if 'item["plan"] = (' not in adapter_source:
        print("FAIL queue does not preserve the atomic classification plan")
        return 1
    if "self._as_agent_turn_lock = asyncio.Lock()" in adapter_source:
        print("FAIL owner-wide agent execution lock remains")
        return 1
    if "async with self._as_agent_turn_lock_for(tid):" not in adapter_source:
        print("FAIL queued turns do not use the conversation execution lock")
        return 1
    sse_handler = adapter_source.split("async def _handle_sse_event", 1)[1]
    sse_handler = sse_handler.split("def _as_inbound_is_admin", 1)[0]
    if "self._as_sequence_inbound_event(data)" not in sse_handler:
        print("FAIL SSE messages bypass the conversation sequencer")
        return 1
    if "asyncio.create_task(self._on_inbound_guarded(data))" in sse_handler.split(
        "def _as_sequence_inbound_event", 1
    )[0]:
        print("FAIL SSE messages still launch unordered guarded handlers")
        return 1
    if "await self._on_inbound_guarded(data)" not in adapter_source.split(
        "async def _as_drain_inbound_events", 1
    )[1].split("def _as_inbound_is_admin", 1)[0]:
        print("FAIL conversation sequencer does not drain guarded handlers")
        return 1
    if "def set_message_handler(self, handler)" not in adapter_source or (
        'setattr(event, "_as_terminal_response", response)' not in adapter_source
    ):
        print("FAIL terminal handler response is not captured per event")
        return 1
    recovery_block = adapter_source.split(
        'logger.warning(\n                            "Zalo: terminal queue response lacked delivery', 1
    )
    if len(recovery_block) != 2 or '"delivery_kind": "queue_recovery"' not in recovery_block[1]:
        print("FAIL missing terminal queue delivery recovery")
        return 1
    if 'raise RuntimeError("terminal queue response delivery failed")' not in recovery_block[1]:
        print("FAIL failed delivery recovery can still acknowledge queue work")
        return 1

    async def verify_conversation_locks() -> bool:
        locks: dict[str, asyncio.Lock] = {}

        def lock_for(thread_id: str) -> asyncio.Lock:
            lock = locks.get(thread_id)
            if lock is None:
                lock = asyncio.Lock()
                locks[thread_id] = lock
            return lock

        entered: list[str] = []
        first_release = asyncio.Event()
        dm_entered = asyncio.Event()
        group_entered = asyncio.Event()

        async def run(name: str, thread_id: str, hold: bool = False) -> None:
            async with lock_for(thread_id):
                entered.append(name)
                if name == "dm-first":
                    dm_entered.set()
                if name == "group-first":
                    group_entered.set()
                if hold:
                    await first_release.wait()

        dm_first = asyncio.create_task(run("dm-first", "dm", hold=True))
        await dm_entered.wait()
        dm_second = asyncio.create_task(run("dm-second", "dm"))
        group_first = asyncio.create_task(run("group-first", "group"))
        await asyncio.wait_for(group_entered.wait(), timeout=1.0)
        await asyncio.sleep(0)
        if "dm-second" in entered:
            return False
        first_release.set()
        await asyncio.gather(dm_first, dm_second, group_first)
        return entered.index("group-first") < entered.index("dm-second")

    if not asyncio.run(verify_conversation_locks()):
        print("FAIL conversation lock isolation")
        return 1
    print("PASS same-conversation serialization + cross-conversation concurrency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
