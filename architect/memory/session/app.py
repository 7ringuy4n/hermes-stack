"""Redis conversation_active session store — Hermes live session SoT.

Keys: conversation_active:{session_id}
TTL from REDIS_CONVERSATION_TTL_SECONDS (default 1d).
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import httpx
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
TTL = int(os.environ.get("REDIS_CONVERSATION_TTL_SECONDS", "86400"))
PREFIX = os.environ.get("SESSION_KEY_PREFIX", "conversation_active")
MEMORY_URL = os.environ.get("MEMORY_URL", "http://memory-manager:8095").rstrip("/")
# Comma-separated Redis key prefixes to wipe on reset-all (no trailing colon).
RESET_PREFIXES = [
    p.strip()
    for p in os.environ.get("SESSION_RESET_PREFIXES", PREFIX).split(",")
    if p.strip()
]

app = FastAPI(title="assistant-session", version="1.2.0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)


class SessionPut(BaseModel):
    session_id: str
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    append: bool = False


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        r.ping()
        return {"ok": True, "ttl": TTL, "prefix": PREFIX}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/v1/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    raw = r.get(f"{PREFIX}:{session_id}")
    if not raw:
        raise HTTPException(404, "not found")
    data = json.loads(raw)
    return {"ok": True, "session": data}


@app.put("/v1/sessions/{session_id}")
def put_session(session_id: str, body: SessionPut) -> dict[str, Any]:
    key = f"{PREFIX}:{session_id}"
    cur: dict[str, Any] = {}
    if body.append:
        raw = r.get(key)
        if raw:
            cur = json.loads(raw)
    messages = list(cur.get("messages") or [])
    if body.append:
        messages.extend(body.messages)
    else:
        messages = body.messages
    # keep last 40 turns
    messages = messages[-40:]
    now = time.time()
    created_at = (cur.get("created_at") if cur else None) or now
    data = {
        "session_id": session_id,
        "thread_id": body.thread_id or cur.get("thread_id"),
        "user_id": body.user_id or cur.get("user_id"),
        "messages": messages,
        "metadata": {**(cur.get("metadata") or {}), **body.metadata},
        "created_at": created_at,
        "updated_at": now,
    }
    r.setex(key, TTL, json.dumps(data, ensure_ascii=False))
    return {"ok": True, "session_id": session_id, "messages": len(messages), "ttl": TTL}


@app.delete("/v1/sessions/{session_id}")
def del_session(session_id: str) -> dict[str, Any]:
    n = r.delete(f"{PREFIX}:{session_id}")
    return {"ok": True, "deleted": int(n)}


@app.post("/v1/sessions/{session_id}/touch")
def touch(session_id: str) -> dict[str, Any]:
    key = f"{PREFIX}:{session_id}"
    if not r.exists(key):
        raise HTTPException(404, "not found")
    r.expire(key, TTL)
    return {"ok": True, "ttl": TTL}


def _scan_delete_prefix(prefix: str) -> int:
    """Delete all keys matching {prefix}:* via SCAN (safe for large keyspaces)."""
    pattern = f"{prefix}:*"
    deleted = 0
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=200)
        if keys:
            deleted += int(r.delete(*keys))
        if cursor == 0:
            break
    return deleted


def _session_blob_to_ltm(data: dict[str, Any]) -> str:
    sid = str(data.get("session_id") or "")
    tid = str(data.get("thread_id") or "")
    uid = str(data.get("user_id") or "")
    msgs = data.get("messages") or []
    lines: list[str] = []
    for m in msgs[-20:]:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or m.get("type") or "user")[:12]
        content = str(m.get("content") or m.get("text") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content[:400]}")
    body = "\n".join(lines).strip()
    if not body:
        return ""
    head = f"[archived session {sid} thread={tid} user={uid}]\n"
    return (head + body)[:3900]


def _archive_sessions_to_ltm() -> dict[str, Any]:
    """Copy live Redis conversations into memory-manager before wipe."""
    archived = 0
    skipped = 0
    errors = 0
    if not MEMORY_URL:
        return {"archived": 0, "skipped": 0, "errors": 0, "reason": "MEMORY_URL empty"}
    for prefix in RESET_PREFIXES:
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match=f"{prefix}:*", count=100)
            for key in keys:
                try:
                    raw = r.get(key)
                    if not raw:
                        skipped += 1
                        continue
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        skipped += 1
                        continue
                    content = _session_blob_to_ltm(data)
                    if len(content) < 20:
                        skipped += 1
                        continue
                    with httpx.Client(timeout=8.0) as c:
                        resp = c.post(
                            f"{MEMORY_URL}/v1/remember",
                            json={
                                "content": content,
                                "type": "event",
                                "importance": 0.55,
                                "source": "clearsession",
                                "session_id": str(data.get("session_id") or ""),
                                "thread_id": str(data.get("thread_id") or ""),
                                "tags": ["archived-session", "clearsession"],
                                "metadata": {"from": "redis", "key": str(key)},
                                "force": True,
                            },
                        )
                    if resp.status_code < 300:
                        archived += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1
            if cursor == 0:
                break
    return {"archived": archived, "skipped": skipped, "errors": errors}


@app.post("/v1/sessions/reset-all")
def reset_all_sessions() -> dict[str, Any]:
    """Archive live Redis sessions to LTM, then wipe — forces a new chat session."""
    archive = _archive_sessions_to_ltm()
    by_prefix: dict[str, int] = {}
    total = 0
    for p in RESET_PREFIXES:
        n = _scan_delete_prefix(p)
        by_prefix[p] = n
        total += n
    return {
        "ok": True,
        "deleted": total,
        "by_prefix": by_prefix,
        "prefixes": RESET_PREFIXES,
        "ltm": archive,
    }


# --- Per-turn timing (Zalo footer) ---
TIMING_PREFIX = "nh:turn"
TIMING_ACTIVE = "nh:turn:active"
TIMING_TTL = 600


class TimingStart(BaseModel):
    thread_id: str
    t0: float
    t_handoff: float
    recv_s: float = 0.0


class TimingAdd(BaseModel):
    field: str  # workflow_s | llm_s
    seconds: float
    thread_id: Optional[str] = None


def _timing_key(thread_id: str) -> str:
    return f"{TIMING_PREFIX}:{thread_id}"


TIMING_CURRENT = "nh:turn:current"
TIMING_CURRENT_TYPE = "nh:turn:current_type"
SENTFILE_PREFIX = "nh:sentfile"
SENTFILE_TTL = 600


def _timing_current() -> Optional[str]:
    """Newest / current Zalo turn — never the oldest stale one."""
    cutoff = time.time() - TIMING_TTL
    try:
        r.zremrangebyscore(TIMING_ACTIVE, "-inf", cutoff)
        cur = r.get(TIMING_CURRENT)
        if cur:
            return str(cur)
        items = r.zrange(TIMING_ACTIVE, -1, -1)
        return str(items[0]) if items else None
    except Exception:
        return None


@app.post("/v1/timing/start")
def timing_start(body: TimingStart) -> dict[str, Any]:
    tid = (body.thread_id or "").strip()
    if not tid:
        raise HTTPException(400, "thread_id required")
    key = _timing_key(tid)
    existing = r.hgetall(key) or {}
    mapping: dict[str, Any] = {
        "t0": body.t0,
        "t_handoff": body.t_handoff,
        "recv_s": body.recv_s,
    }
    # Do not zero workflow_s/llm_s — dispatcher may have already recorded.
    if not existing:
        mapping["workflow_s"] = 0
        mapping["llm_s"] = 0
    r.hset(key, mapping=mapping)
    r.expire(key, TIMING_TTL)
    r.zadd(TIMING_ACTIVE, {tid: body.t_handoff or time.time()})
    r.set(TIMING_CURRENT, tid, ex=TIMING_TTL)
    return {"ok": True, "thread_id": tid}


class TurnDest(BaseModel):
    thread_id: str
    thread_type: str = "user"


class FileClaim(BaseModel):
    key: str
    thread_id: str = ""


@app.post("/v1/turn/dest")
def turn_dest_set(body: TurnDest) -> dict[str, Any]:
    """Remember which Zalo thread asked — outbound files must go here only."""
    tid = (body.thread_id or "").strip()
    if not tid:
        raise HTTPException(400, "thread_id required")
    tt = body.thread_type if body.thread_type in {"user", "group"} else "user"
    r.set(TIMING_CURRENT, tid, ex=TIMING_TTL)
    r.set(TIMING_CURRENT_TYPE, tt, ex=TIMING_TTL)
    return {"ok": True, "thread_id": tid, "thread_type": tt}


@app.get("/v1/turn/dest")
def turn_dest_get() -> dict[str, Any]:
    tid = r.get(TIMING_CURRENT)
    tt = r.get(TIMING_CURRENT_TYPE)
    if isinstance(tid, (bytes, bytearray)):
        tid = tid.decode()
    if isinstance(tt, (bytes, bytearray)):
        tt = tt.decode()
    return {
        "ok": bool(tid),
        "thread_id": str(tid or ""),
        "thread_type": tt if tt in {"user", "group"} else "user",
    }


@app.post("/v1/files/claim")
def file_claim(body: FileClaim) -> dict[str, Any]:
    """First caller owns this generated file for 10 minutes (no duplicate Zalo send)."""
    key = (body.key or "").strip()
    if not key:
        raise HTTPException(400, "key required")
    redis_key = f"{SENTFILE_PREFIX}:{key}"
    first = bool(r.set(redis_key, body.thread_id or "1", nx=True, ex=SENTFILE_TTL))
    owner = r.get(redis_key)
    if isinstance(owner, (bytes, bytearray)):
        owner = owner.decode()
    return {"ok": True, "first": first, "owner": str(owner or "")}


@app.post("/v1/timing/add")
def timing_add(body: TimingAdd) -> dict[str, Any]:
    field = (body.field or "").strip()
    if field not in {"workflow_s", "llm_s"}:
        raise HTTPException(400, "field must be workflow_s or llm_s")
    sec = float(body.seconds or 0)
    if sec < 0:
        sec = 0.0
    tid = (body.thread_id or "").strip() or _timing_current()
    if not tid:
        return {"ok": False, "error": "no active turn"}
    key = _timing_key(tid)
    r.hincrbyfloat(key, field, sec)
    r.expire(key, TIMING_TTL)
    return {"ok": True, "thread_id": tid, "field": field, "seconds": sec}


@app.post("/v1/timing/{thread_id}/finish")
def timing_finish(thread_id: str) -> dict[str, Any]:
    tid = (thread_id or "").strip()
    key = _timing_key(tid)
    raw = r.hgetall(key)
    r.delete(key)
    r.zrem(TIMING_ACTIVE, tid)
    try:
        cur = r.get(TIMING_CURRENT)
        if cur is not None and (cur.decode() if isinstance(cur, (bytes, bytearray)) else str(cur)) == tid:
            r.delete(TIMING_CURRENT)
    except Exception:
        pass
    data = {}
    for k, v in (raw or {}).items():
        kk = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
        try:
            data[kk] = float(v)
        except (TypeError, ValueError):
            continue
    return {"ok": True, "thread_id": tid, "timing": data}
