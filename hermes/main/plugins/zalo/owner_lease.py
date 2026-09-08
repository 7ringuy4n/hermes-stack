"""Small async Valkey lease for singleton Zalo bridge ownership.

Uses the Redis wire protocol directly so the plugin does not add a redis-py
runtime dependency. The token check makes renewal and release owner-safe.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import socket
import threading
import time
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
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_last_success = 0.0
        self._ownership_lost = False

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
        self.stop_heartbeat()
        script = (
            "if redis.call('get',KEYS[1]) == ARGV[1] then "
            "return redis.call('del',KEYS[1]) else return 0 end"
        )
        await self._execute("EVAL", script, "1", self.key, self.token)

    def _sync_reply(self, stream):
        prefix = stream.read(1)
        line = stream.readline().rstrip(b"\r\n")
        if prefix == b"+":
            return line.decode("utf-8", "replace")
        if prefix == b":":
            return int(line)
        if prefix == b"$":
            size = int(line)
            if size < 0:
                return None
            data = stream.read(size)
            stream.read(2)
            return data.decode("utf-8", "replace")
        if prefix == b"-":
            raise RuntimeError(line.decode("utf-8", "replace"))
        raise RuntimeError("unsupported Valkey response")

    def _sync_execute(self, *parts: str):
        with socket.create_connection((self.host, self.port), timeout=5.0) as conn:
            conn.settimeout(5.0)
            stream = conn.makefile("rb")
            if self.password:
                auth = ("AUTH", self.username, self.password) if self.username else ("AUTH", self.password)
                conn.sendall(_command(*auth))
                self._sync_reply(stream)
            if self.database:
                conn.sendall(_command("SELECT", str(self.database)))
                self._sync_reply(stream)
            conn.sendall(_command(*parts))
            return self._sync_reply(stream)

    def _sync_renew(self) -> bool:
        script = (
            "if redis.call('get',KEYS[1]) == ARGV[1] then "
            "return redis.call('expire',KEYS[1],ARGV[2]) else return 0 end"
        )
        return int(
            self._sync_execute(
                "EVAL", script, "1", self.key, self.token, str(self.ttl_s)
            )
            or 0
        ) == 1

    def start_heartbeat(self) -> None:
        """Renew independently from the gateway event loop.

        Some provider clients execute synchronous work inside the gateway loop.
        A daemon thread prevents that work from creating a false HA failover.
        """
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._ownership_lost = False
        self._heartbeat_last_success = time.monotonic()
        interval = max(5.0, float(self.ttl_s) / 3.0)

        def _run() -> None:
            delay = interval
            while not self._heartbeat_stop.wait(delay):
                try:
                    if not self._sync_renew():
                        self._ownership_lost = True
                        return
                    self._heartbeat_last_success = time.monotonic()
                    delay = interval
                except Exception:
                    if time.monotonic() - self._heartbeat_last_success >= self.ttl_s:
                        self._ownership_lost = True
                        return
                    delay = 2.0

        self._heartbeat_thread = threading.Thread(
            target=_run,
            name="zalo-owner-lease",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._heartbeat_thread = None

    def heartbeat_healthy(self) -> bool:
        if self._ownership_lost:
            return False
        if self._heartbeat_last_success <= 0:
            return False
        return time.monotonic() - self._heartbeat_last_success < self.ttl_s
