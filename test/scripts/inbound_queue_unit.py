# -*- coding: utf-8 -*-
"""Unit tests for Valkey inbound FIFO helpers (no VPS, no Valkey)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

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

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PLENTY_SCHEDULE = (
    "1. Send daily message to wakeup every in DM/group: * a 6:00 AM GMT +7\n"
    "2. Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế\n"
    "3. Cập nhật ngắn gọn nội dung giá xăng E5 RON92 và E10 RON95 gần nhất"
)

PLENTY_NOW = (
    "1. Chào buổi sáng trong DM\n"
    "2. Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế\n"
    "3. Cập nhật ngắn gọn nội dung giá xăng E5 RON92 và E10 RON95 gần nhất"
)


def main() -> int:
    if DEFAULT_MAX != 3 or queue_max() != 3:
        print(f"FAIL default cap {DEFAULT_MAX} queue_max={queue_max()} want 3")
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
