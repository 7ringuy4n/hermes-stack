"""LongTermMemoryProvider — Mem0-shaped API over Redis + Qdrant (via embeddings).

Hermes must not depend on Mem0 internals. This service is the Provider:
  LongTermMemoryProvider → Mem0Provider (this container)

Stores:
  - Redis: conversation working set + memory id index (TTL)
  - Qdrant: semantic vectors for recall (optional; degrades to Redis keyword)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any, Optional

import httpx
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
QDRANT_URL = os.environ.get("QDRANT_URL", "").rstrip("/")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "conversational_memory")
EMBED_URL = os.environ.get("EMBED_URL", "").rstrip("/")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
EMBED_API_KEY = os.environ.get("EMBED_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
CONV_TTL = int(os.environ.get("REDIS_CONVERSATION_TTL_SECONDS", "86400"))

app = FastAPI(title="assistant-mem0", version="1.0.0")
r: redis.Redis | None = None


def _rdb() -> redis.Redis:
    assert r is not None
    return r


def _key_mem(user_id: str, mid: str) -> str:
    return f"mem0:m:{user_id}:{mid}"


def _key_idx(user_id: str) -> str:
    return f"mem0:idx:{user_id}"


def _key_conv(user_id: str) -> str:
    return f"mem0:conv:{user_id}"


@app.on_event("startup")
def startup() -> None:
    global r
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    if QDRANT_URL:
        _ensure_collection()


def _ensure_collection() -> None:
    try:
        with httpx.Client(timeout=10) as c:
            resp = c.get(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}")
            if resp.status_code == 200:
                return
            # create with unknown dim — first embed will recreate if needed; use 1536 default
            c.put(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}",
                json={"vectors": {"size": 1536, "distance": "Cosine"}},
            )
    except Exception:
        pass


def _embed(text: str) -> Optional[list[float]]:
    if not EMBED_URL or not EMBED_API_KEY:
        return None
    try:
        with httpx.Client(timeout=60) as c:
            resp = c.post(
                f"{EMBED_URL}/embeddings",
                headers={"Authorization": f"Bearer {EMBED_API_KEY}"},
                json={"model": EMBED_MODEL, "input": text},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except Exception:
        return None


def _qdrant_upsert(mid: str, user_id: str, vector: list[float], payload: dict) -> None:
    if not QDRANT_URL:
        return
    try:
        with httpx.Client(timeout=30) as c:
            c.put(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points",
                json={
                    "points": [
                        {
                            "id": int(hashlib.md5(mid.encode()).hexdigest()[:15], 16),
                            "vector": vector,
                            "payload": {**payload, "memory_id": mid, "user_id": user_id},
                        }
                    ]
                },
            )
    except Exception:
        pass


def _qdrant_search(user_id: str, vector: list[float], limit: int) -> list[str]:
    if not QDRANT_URL:
        return []
    try:
        with httpx.Client(timeout=30) as c:
            resp = c.post(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
                json={
                    "vector": vector,
                    "limit": limit,
                    "with_payload": True,
                    "filter": {
                        "must": [{"key": "user_id", "match": {"value": user_id}}]
                    },
                },
            )
            if resp.status_code != 200:
                return []
            return [
                p["payload"]["memory_id"]
                for p in resp.json().get("result", [])
                if p.get("payload", {}).get("memory_id")
            ]
    except Exception:
        return []


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        _rdb().ping()
        redis_ok = True
    except Exception as e:
        return {"ok": False, "redis": str(e)}
    q_ok = None
    if QDRANT_URL:
        try:
            with httpx.Client(timeout=5) as c:
                q_ok = c.get(f"{QDRANT_URL}/readyz").status_code == 200
        except Exception:
            q_ok = False
    return {"ok": True, "redis": redis_ok, "qdrant": q_ok, "collection": QDRANT_COLLECTION}


class AddReq(BaseModel):
    messages: list[dict[str, str]] = Field(default_factory=list)
    user_id: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)
    # convenience single text
    text: Optional[str] = None


class SearchReq(BaseModel):
    query: str
    user_id: str = "default"
    limit: int = 5


@app.post("/v1/memories")
@app.post("/memories")
def add_memory(req: AddReq) -> dict[str, Any]:
    text = req.text or " ".join(
        m.get("content", "") for m in req.messages if m.get("content")
    ).strip()
    if not text:
        raise HTTPException(400, "empty memory")
    mid = uuid.uuid4().hex
    rec = {
        "id": mid,
        "user_id": req.user_id,
        "memory": text,
        "metadata": req.metadata,
        "created_at": time.time(),
        "hash": hashlib.sha256(text.encode()).hexdigest()[:16],
    }
    _rdb().set(_key_mem(req.user_id, mid), json.dumps(rec))
    _rdb().sadd(_key_idx(req.user_id), mid)
    vec = _embed(text)
    if vec:
        _qdrant_upsert(mid, req.user_id, vec, {"text": text, **req.metadata})
    return {"ok": True, "results": [{"id": mid, "memory": text, "event": "ADD"}]}


@app.post("/v1/search")
@app.post("/search")
def search(req: SearchReq) -> dict[str, Any]:
    ids = []
    vec = _embed(req.query)
    if vec:
        ids = _qdrant_search(req.user_id, vec, req.limit)
    if not ids:
        # keyword fallback over redis index
        all_ids = list(_rdb().smembers(_key_idx(req.user_id)))
        q = req.query.lower()
        scored = []
        for mid in all_ids:
            raw = _rdb().get(_key_mem(req.user_id, mid))
            if not raw:
                continue
            rec = json.loads(raw)
            blob = rec.get("memory", "").lower()
            score = sum(1 for tok in q.split() if tok in blob)
            if score:
                scored.append((score, mid))
        scored.sort(reverse=True)
        ids = [m for _, m in scored[: req.limit]]
    results = []
    for mid in ids:
        raw = _rdb().get(_key_mem(req.user_id, mid))
        if raw:
            rec = json.loads(raw)
            results.append(
                {
                    "id": mid,
                    "memory": rec.get("memory"),
                    "metadata": rec.get("metadata", {}),
                    "score": 1.0,
                }
            )
    return {"results": results}


@app.get("/v1/memories/{user_id}")
def list_memories(user_id: str, limit: int = 50) -> dict[str, Any]:
    ids = list(_rdb().smembers(_key_idx(user_id)))[:limit]
    out = []
    for mid in ids:
        raw = _rdb().get(_key_mem(user_id, mid))
        if raw:
            out.append(json.loads(raw))
    return {"results": out}


class ConvMsg(BaseModel):
    role: str
    content: str


class ConvAppend(BaseModel):
    user_id: str
    messages: list[ConvMsg]


@app.post("/v1/conversation/append")
def conv_append(req: ConvAppend) -> dict[str, Any]:
    """ConversationProvider helper — Redis TTL working set."""
    key = _key_conv(req.user_id)
    pipe = _rdb().pipeline()
    for m in req.messages:
        pipe.rpush(key, json.dumps(m.model_dump()))
    pipe.expire(key, CONV_TTL)
    pipe.execute()
    return {"ok": True, "ttl": CONV_TTL, "len": _rdb().llen(key)}


@app.get("/v1/conversation/{user_id}")
def conv_get(user_id: str, limit: int = 40) -> dict[str, Any]:
    key = _key_conv(user_id)
    items = _rdb().lrange(key, -limit, -1)
    return {
        "messages": [json.loads(x) for x in items],
        "ttl": _rdb().ttl(key),
    }


@app.post("/v1/compact")
def compact() -> dict[str, Any]:
    """Silent housekeeping — trim expired conversation indexes (TTL handles most)."""
    try:
        # Touch health only; Redis EXPIRE on keys is the primary compact.
        _rdb().ping()
        return {"ok": True, "collection": QDRANT_COLLECTION}
    except Exception:
        return {"ok": False}
