"""Isolated Hermes sessions + wait-until-idle for Zalo workflow jobs.

``BasePlatformAdapter.handle_message`` returns quickly and runs the agent in a
background task. Sequential jobs that share one session key get queued as
pending follow-ups. Isolated chat ids (`{thread}::job::{job_id}`) give each
job its own gateway session so numbered items can run in parallel and each
still send its own Zalo reply. Send paths map the isolated id back to the
real thread.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Mapping, Optional

DEFAULT_TIMEOUT_S = 420.0
ARM_S = 1.5
POLL_S = 0.4
PULSE_EVERY_S = 25.0
JOB_SESSION_MARK = "::job::"

ActiveGet = Callable[[], Optional[Mapping[Any, Any]]]
PulseFn = Callable[[], None]


def isolate_session_chat_id(thread_id: str, job_id: str) -> str:
    tid = str(thread_id or "").strip()
    jid = str(job_id or "").strip()
    if not tid:
        return tid
    if JOB_SESSION_MARK in tid:
        return tid
    if not jid:
        return tid
    return f"{tid}{JOB_SESSION_MARK}{jid}"


def real_thread_id(chat_id: str) -> str:
    raw = str(chat_id or "")
    if JOB_SESSION_MARK in raw:
        return raw.split(JOB_SESSION_MARK, 1)[0]
    return raw


def is_isolated_session(chat_id: str) -> bool:
    return JOB_SESSION_MARK in str(chat_id or "")


def session_active_for_thread(
    active: Optional[Mapping[Any, Any]],
    thread_id: str,
) -> bool:
    tid = str(thread_id or "").strip()
    if not tid or not isinstance(active, dict) or not active:
        return False
    return any(tid in str(k) for k in active)


async def wait_thread_idle(
    active_get: ActiveGet,
    thread_id: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    poll_s: float = POLL_S,
    pulse: Optional[PulseFn] = None,
    pulse_every_s: float = PULSE_EVERY_S,
    arm_first: bool = False,
    arm_s: float = ARM_S,
) -> bool:
    """Return True if the thread became idle before timeout.

    ``arm_first=True`` (after ``handle_message``): wait a short arming window
    for the session to appear. If it never does, treat as idle. If it does,
    wait until it clears.
    """
    timeout_s = max(1.0, float(timeout_s))
    poll_s = max(0.05, float(poll_s))
    arm_s = max(0.05, float(arm_s))
    pulse_every_s = max(0.05, float(pulse_every_s))
    loop = asyncio.get_running_loop()
    start = loop.time()
    deadline = start + timeout_s
    last_pulse = start
    saw_active = not arm_first

    while True:
        now = loop.time()
        active = session_active_for_thread(active_get(), thread_id)
        if active:
            saw_active = True
        if arm_first and not saw_active:
            if (now - start) >= arm_s:
                return True
        elif not active:
            return True
        if now >= deadline:
            return False
        if pulse is not None and (now - last_pulse) >= pulse_every_s:
            last_pulse = now
            try:
                pulse()
            except Exception:
                pass
        remaining = deadline - now
        await asyncio.sleep(min(poll_s, remaining))
