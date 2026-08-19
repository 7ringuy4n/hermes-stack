# -*- coding: utf-8 -*-
"""Unit: wait for Hermes gateway session idle before the next workflow job."""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from turn_wait import session_active_for_thread, wait_thread_idle  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TID = "thread-test-1"


def test_session_match() -> None:
    from turn_wait import isolate_session_chat_id, is_isolated_session, real_thread_id

    active = {f"zalo:dm:{TID}": object()}
    if not session_active_for_thread(active, TID):
        raise SystemExit("FAIL match thread in session key")
    if session_active_for_thread(active, "other-thread"):
        raise SystemExit("FAIL other thread should be idle")
    if session_active_for_thread({}, TID):
        raise SystemExit("FAIL empty map")
    if session_active_for_thread(None, TID):
        raise SystemExit("FAIL none map")
    iso = isolate_session_chat_id(TID, "job_ab")
    if not is_isolated_session(iso) or real_thread_id(iso) != TID:
        raise SystemExit(f"FAIL isolate {iso}")
    from turn_wait import same_dest_thread

    if not same_dest_thread(iso, TID) or not same_dest_thread(TID, iso):
        raise SystemExit("FAIL same_dest_thread isolated vs real")
    if same_dest_thread(iso, "other-thread"):
        raise SystemExit("FAIL same_dest_thread other")
    if same_dest_thread("", TID):
        raise SystemExit("FAIL same_dest_thread empty")
    iso_active = {f"zalo:dm:{iso}": object()}
    if not session_active_for_thread(iso_active, iso):
        raise SystemExit("FAIL isolated session match")
    other = isolate_session_chat_id(TID, "job_cd")
    if session_active_for_thread(iso_active, other):
        raise SystemExit("FAIL sibling job should not share session")
    print("PASS session_active_for_thread")


async def _idle_cases() -> None:
    box: dict = {}

    ok = await wait_thread_idle(lambda: box, TID, timeout_s=1.0, poll_s=0.05)
    if not ok:
        raise SystemExit("FAIL already idle")

    box[f"zalo:dm:{TID}"] = object()

    async def _clear() -> None:
        await asyncio.sleep(0.2)
        box.clear()

    task = asyncio.create_task(_clear())
    ok = await wait_thread_idle(lambda: box, TID, timeout_s=2.0, poll_s=0.05)
    await task
    if not ok:
        raise SystemExit("FAIL wait until clear")

    box[f"zalo:dm:{TID}"] = object()
    ok = await wait_thread_idle(lambda: box, TID, timeout_s=0.25, poll_s=0.05)
    if ok:
        raise SystemExit("FAIL timeout should be False while still active")
    box.clear()

    pulses = {"n": 0}

    def _pulse() -> None:
        pulses["n"] += 1

    box[f"zalo:dm:{TID}"] = object()

    async def _clear_slow() -> None:
        await asyncio.sleep(0.35)
        box.clear()

    task = asyncio.create_task(_clear_slow())
    ok = await wait_thread_idle(
        lambda: box,
        TID,
        timeout_s=2.0,
        poll_s=0.05,
        pulse=_pulse,
        pulse_every_s=0.1,
    )
    await task
    if not ok or pulses["n"] < 1:
        raise SystemExit(f"FAIL pulse n={pulses['n']} ok={ok}")

    # After handle_message: session never appears → idle after arm window.
    ok = await wait_thread_idle(
        lambda: {},
        TID,
        timeout_s=2.0,
        poll_s=0.05,
        arm_first=True,
        arm_s=0.15,
    )
    if not ok:
        raise SystemExit("FAIL arm_first never-started")

    box[f"zalo:dm:{TID}"] = object()

    async def _clear_armed() -> None:
        await asyncio.sleep(0.2)
        box.clear()

    task = asyncio.create_task(_clear_armed())
    ok = await wait_thread_idle(
        lambda: box,
        TID,
        timeout_s=2.0,
        poll_s=0.05,
        arm_first=True,
        arm_s=0.05,
    )
    await task
    if not ok:
        raise SystemExit("FAIL arm_first then idle")
    print("PASS wait_thread_idle")


def main() -> int:
    test_session_match()
    asyncio.run(_idle_cases())
    print("PASS workflow turn wait")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
