#!/usr/bin/env python3
"""Unit checks for renewable, owner-safe Zalo Valkey lease behavior."""
from __future__ import annotations

import asyncio
import time
import types
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[2]
LEASE_SOURCE = ROOT / "hermes" / "main" / "plugins" / "zalo" / "owner_lease.py"
lease_module = types.ModuleType("owner_lease_source")
exec(compile(LEASE_SOURCE.read_text(encoding="utf-8"), str(LEASE_SOURCE), "exec"), lease_module.__dict__)
ValkeyLease = lease_module.ValkeyLease


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
        "adapter heartbeat API is complete": all(
            callable(getattr(lease, method, None))
            for method in ("start_heartbeat", "stop_heartbeat", "heartbeat_healthy")
        ),
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
    lease._heartbeat_last_success = time.monotonic()
    checks["fresh heartbeat healthy"] = lease.heartbeat_healthy()
    lease._ownership_lost = True
    checks["lost token fenced"] = not lease.heartbeat_healthy()
    lease._ownership_lost = False
    lease._heartbeat_last_success = time.monotonic() - lease.ttl_s
    checks["expired heartbeat fenced"] = not lease.heartbeat_healthy()

    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return all(checks.values())


def main() -> int:
    return 0 if asyncio.run(verify()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
