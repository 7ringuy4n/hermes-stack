#!/usr/bin/env python3
"""Unit checks for renewable, owner-safe Zalo Valkey lease behavior."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from owner_lease import ValkeyLease  # noqa: E402


async def verify() -> bool:
    lease = ValkeyLease("redis://worker:secret@valkey.internal:6380/2", "zalo:test:owner", 45, "replica-a")
    checks = {
        "host parsed": lease.host == "valkey.internal",
        "port parsed": lease.port == 6380,
        "database parsed": lease.database == 2,
        "username parsed": lease.username == "worker",
        "password parsed": lease.password == "secret",
        "lease bounded": lease.ttl_s == 45,
        "unique owner token": lease.token.startswith("replica-a:"),
    }

    lease._execute = AsyncMock(side_effect=["OK", 1, 1])  # type: ignore[method-assign]
    checks["acquire SET NX EX"] = await lease.acquire()
    checks["owner-safe renew"] = await lease.renew()
    await lease.release()
    calls = [tuple(call.args) for call in lease._execute.await_args_list]
    checks["acquire command"] = calls[0] == (
        "SET", "zalo:test:owner", lease.token, "NX", "EX", "45"
    )
    checks["renew uses compare script"] = calls[1][0] == "EVAL" and lease.token in calls[1]
    checks["release uses compare script"] = calls[2][0] == "EVAL" and lease.token in calls[2]

    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return all(checks.values())


def main() -> int:
    return 0 if asyncio.run(verify()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
