#!/usr/bin/env python3
"""Valkey gate store — reusable rate-limit + answering slots + inbound FIFO.

Talks Redis protocol (Valkey). Logic lives in the server (INCR / EXPIRE / Lua).
Enable/disable is the caller's env (max_n=0 skips). Fail-open if Valkey is down.

Usage:
  from gate_valkey import GateStore
  st = GateStore.from_env()
  over, notify = st.rate_take(user_id, chat_id, max_n=1, window_s=10)
  ok = st.answering_try(chat_id, max_n=3, ttl_s=45)
  st.answering_done(chat_id)
  st.queue_push(chat_id, payload, max_n=20, ttl_s=3600)
"""
from __future__ import annotations

import os
import socket
import threading
from typing import Optional, Tuple
from urllib.parse import urlparse

RATE_LUA = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return n
"""

TRY_LUA = """
local n = tonumber(redis.call('GET', KEYS[1]) or '0')
local cap = tonumber(ARGV[1])
if n >= cap then
  return 0
end
n = redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 1
"""

DONE_LUA = """
local n = tonumber(redis.call('GET', KEYS[1]) or '0')
if n <= 1 then
  redis.call('DEL', KEYS[1])
  return 0
end
return redis.call('DECR', KEYS[1])
"""

PUSH_LUA = """
local cap = tonumber(ARGV[2])
local n = redis.call('LLEN', KEYS[1])
if cap > 0 and n >= cap then
  return -1
end
redis.call('RPUSH', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return n + 1
"""


class _Resp:
    """Minimal Redis/Valkey RESP client (stdlib)."""

    def __init__(self, host: str, port: int, db: int, timeout: float = 0.4) -> None:
        self.host = host
        self.port = port
        self.db = db
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _connect(self) -> socket.socket:
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        s.settimeout(self.timeout)
        if self.db:
            self._raw(s, ["SELECT", str(self.db)])
        return s

    def _raw(self, s: socket.socket, parts: list) -> object:
        chunks = [f"*{len(parts)}\r\n".encode("ascii")]
        for p in parts:
            if isinstance(p, bytes):
                b = p
            else:
                b = str(p).encode("utf-8")
            chunks.append(f"${len(b)}\r\n".encode("ascii"))
            chunks.append(b)
            chunks.append(b"\r\n")
        s.sendall(b"".join(chunks))
        return self._read(s)

    def _read(self, s: socket.socket) -> object:
        line = self._readline(s)
        if not line:
            raise ConnectionError("empty")
        kind, rest = line[:1], line[1:]
        if kind == b"+":
            return rest.decode("utf-8")
        if kind == b"-":
            raise RuntimeError(rest.decode("utf-8", "replace"))
        if kind == b":":
            return int(rest)
        if kind == b"$":
            n = int(rest)
            if n < 0:
                return None
            data = self._readexact(s, n + 2)
            return data[:-2]
        if kind == b"*":
            n = int(rest)
            if n < 0:
                return None
            return [self._read(s) for _ in range(n)]
        raise RuntimeError("bad RESP")

    def _readline(self, s: socket.socket) -> bytes:
        buf = b""
        while not buf.endswith(b"\r\n"):
            ch = s.recv(1)
            if not ch:
                break
            buf += ch
        return buf[:-2]

    def _readexact(self, s: socket.socket, n: int) -> bytes:
        out = b""
        while len(out) < n:
            chunk = s.recv(n - len(out))
            if not chunk:
                raise ConnectionError("short")
            out += chunk
        return out

    def call(self, *parts: object) -> object:
        with self._lock:
            if self._sock is None:
                self._sock = self._connect()
            try:
                return self._raw(self._sock, list(parts))
            except (OSError, ConnectionError, TimeoutError, RuntimeError):
                self.close()
                self._sock = self._connect()
                return self._raw(self._sock, list(parts))


class GateStore:
    """Rate window + answering slots. Prefix is namespaced for reuse."""

    def __init__(self, url: str, prefix: str = "assistant:gate") -> None:
        u = urlparse(url)
        host = u.hostname or "127.0.0.1"
        port = int(u.port or 6379)
        db = 0
        if u.path and u.path.strip("/"):
            try:
                db = int(u.path.strip("/").split("/")[0])
            except ValueError:
                db = 0
        self._r = _Resp(host, port, db)
        self.prefix = (prefix or "assistant:gate").rstrip(":")

    @classmethod
    def from_env(cls) -> Optional["GateStore"]:
        raw = (os.getenv("ASSISTANT_STORE_URL") or os.getenv("REDIS_URL") or "").strip()
        if not raw or raw.lower() in {"0", "off", "false", "no"}:
            return None
        prefix = (os.getenv("ASSISTANT_STORE_PREFIX") or "assistant:gate").strip() or "assistant:gate"
        try:
            st = cls(raw, prefix=prefix)
            st._r.call("PING")
            return st
        except Exception:
            return None

    def _k(self, *parts: str) -> str:
        return self.prefix + ":" + ":".join(str(p) for p in parts)

    def rate_take(self, user_id: str, chat_id: str, max_n: int, window_s: float) -> Tuple[bool, bool]:
        """Returns (over_limit, should_notify). max_n<=0 means disabled."""
        if max_n <= 0:
            return False, False
        win = max(3, int(window_s))
        key = self._k("rate", user_id, chat_id)
        note = self._k("rate_note", user_id, chat_id)
        n = int(self._r.call("EVAL", RATE_LUA, 1, key, str(win)) or 0)
        if n <= max_n:
            return False, False
        got = self._r.call("SET", note, "1", "NX", "EX", str(win))
        notify = got in (b"OK", "OK", True)
        return True, bool(notify)

    def answering_try(self, chat_id: str, max_n: int, ttl_s: int = 45) -> bool:
        """True = took a slot. max_n<=0 means disabled (always True)."""
        if max_n <= 0:
            return True
        key = self._k("ans", chat_id)
        ttl = max(15, int(ttl_s))
        got = int(self._r.call("EVAL", TRY_LUA, 1, key, str(max_n), str(ttl)) or 0)
        return got == 1

    def answering_done(self, chat_id: str) -> None:
        key = self._k("ans", chat_id)
        try:
            self._r.call("EVAL", DONE_LUA, 1, key)
        except Exception:
            pass

    def queue_push(self, chat_id: str, payload: str, max_n: int, ttl_s: int) -> int:
        """RPUSH FIFO. Returns new length, or -1 if at cap."""
        key = self._k("q", chat_id)
        cap = max(0, int(max_n))
        ttl = max(60, int(ttl_s))
        got = self._r.call("EVAL", PUSH_LUA, 1, key, payload, str(cap), str(ttl))
        return int(got if got is not None else -1)

    def queue_push_front(self, chat_id: str, payload: str, ttl_s: int) -> None:
        key = self._k("q", chat_id)
        ttl = max(60, int(ttl_s))
        self._r.call("LPUSH", key, payload)
        self._r.call("EXPIRE", key, str(ttl))

    def queue_pop(self, chat_id: str) -> Optional[str]:
        key = self._k("q", chat_id)
        raw = self._r.call("LPOP", key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8", "replace")
        return str(raw)

    def queue_len(self, chat_id: str) -> int:
        key = self._k("q", chat_id)
        return int(self._r.call("LLEN", key) or 0)

    def queue_seen(self, message_id: str, ttl_s: int = 600) -> bool:
        """True if this message_id is new (should enqueue)."""
        mid = str(message_id or "").strip()
        if not mid:
            return True
        key = self._k("qseen", mid)
        ttl = max(60, int(ttl_s))
        got = self._r.call("SET", key, "1", "NX", "EX", str(ttl))
        return got in (b"OK", "OK", True)

    def worker_try(self, chat_id: str, ttl_s: int = 300) -> bool:
        key = self._k("qwork", chat_id)
        ttl = max(30, int(ttl_s))
        got = self._r.call("SET", key, "1", "NX", "EX", str(ttl))
        return got in (b"OK", "OK", True)

    def worker_touch(self, chat_id: str, ttl_s: int = 300) -> None:
        key = self._k("qwork", chat_id)
        try:
            self._r.call("EXPIRE", key, str(max(30, int(ttl_s))))
        except Exception:
            pass

    def worker_done(self, chat_id: str) -> None:
        key = self._k("qwork", chat_id)
        try:
            self._r.call("DEL", key)
        except Exception:
            pass

    def attachment_put(self, chat_id: str, payload: str, ttl_s: int) -> None:
        """Remember the last extracted attachment text for follow-up turns."""
        key = self._k("attach", chat_id)
        try:
            self._r.call("SET", key, payload, "EX", str(max(30, int(ttl_s))))
        except Exception:
            pass

    def attachment_get(self, chat_id: str) -> Optional[str]:
        key = self._k("attach", chat_id)
        try:
            raw = self._r.call("GET", key)
        except Exception:
            return None
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8", "replace")
        return str(raw)

    def attachment_clear(self, chat_id: str) -> None:
        key = self._k("attach", chat_id)
        try:
            self._r.call("DEL", key)
        except Exception:
            pass


def get_store() -> Optional[GateStore]:
    return GateStore.from_env()
