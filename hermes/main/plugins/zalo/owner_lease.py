"""Small async Valkey lease for singleton Zalo bridge ownership.

Uses the Redis wire protocol directly so the plugin does not add a redis-py
runtime dependency. The token check makes renewal and release owner-safe.
"""
from __future__ import annotations

import asyncio
import os
import secrets
from urllib.parse import urlsplit


def _command(*parts: str) -> bytes:
    encoded = [str(part).encode("utf-8") for part in parts]
    body = [f"*{len(encoded)}\r\n".encode("ascii")]
    for part in encoded:
        body.extend((f"${len(part)}\r\n".encode("ascii"), part, b"\r\n"))
    return b"".join(body)


async def _reply(reader: asyncio.StreamReader):
    prefix = await reader.readexactly(1)
    line = (await reader.readline()).rstrip(b"\r\n")
    if prefix == b"+":
        return line.decode("utf-8", "replace")
    if prefix == b":":
        return int(line)
    if prefix == b"$":
        size = int(line)
        if size < 0:
            return None
        data = await reader.readexactly(size)
        await reader.readexactly(2)
        return data.decode("utf-8", "replace")
    if prefix == b"-":
        raise RuntimeError(line.decode("utf-8", "replace"))
    raise RuntimeError("unsupported Valkey response")


class ValkeyLease:
    def __init__(self, url: str, key: str, ttl_s: int, owner: str):
        parsed = urlsplit(url)
        self.host = parsed.hostname or "valkey"
        self.port = parsed.port or 6379
        self.username = parsed.username or ""
        self.password = parsed.password or ""
        path = (parsed.path or "/0").strip("/")
        self.database = int(path) if path.isdigit() else 0
        self.key = key
        self.ttl_s = max(15, ttl_s)
        self.token = f"{owner}:{secrets.token_hex(12)}"

    @classmethod
    def from_env(cls, owner: str) -> "ValkeyLease":
        return cls(
            os.getenv("VALKEY_URL") or os.getenv("REDIS_URL") or "redis://valkey:6379/0",
            os.getenv("ZALO_OWNER_LEASE_KEY") or "zalo:bridge:owner",
            int(os.getenv("ZALO_OWNER_LEASE_TTL_S") or "45"),
            owner,
        )

    async def _execute(self, *parts: str):
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=5
        )
        try:
            if self.password:
                auth = ("AUTH", self.username, self.password) if self.username else ("AUTH", self.password)
                writer.write(_command(*auth))
                await writer.drain()
                await _reply(reader)
            if self.database:
                writer.write(_command("SELECT", str(self.database)))
                await writer.drain()
                await _reply(reader)
            writer.write(_command(*parts))
            await writer.drain()
            return await asyncio.wait_for(_reply(reader), timeout=5)
        finally:
            writer.close()
            await writer.wait_closed()

    async def acquire(self) -> bool:
        result = await self._execute(
            "SET", self.key, self.token, "NX", "EX", str(self.ttl_s)
        )
        return result == "OK"

    async def renew(self) -> bool:
        script = (
            "if redis.call('get',KEYS[1]) == ARGV[1] then "
            "return redis.call('expire',KEYS[1],ARGV[2]) else return 0 end"
        )
        return int(
            await self._execute(
                "EVAL", script, "1", self.key, self.token, str(self.ttl_s)
            )
            or 0
        ) == 1

    async def release(self) -> None:
        script = (
            "if redis.call('get',KEYS[1]) == ARGV[1] then "
            "return redis.call('del',KEYS[1]) else return 0 end"
        )
        await self._execute("EVAL", script, "1", self.key, self.token)
