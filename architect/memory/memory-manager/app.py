"""assistant Memory Manager — Postgres SoT, optional Qdrant index.

Layers:
  working   — ephemeral hints for current turn (not persisted here)
  episodic  — events / interactions
  semantic  — facts / decisions / preferences (long-term)
  procedural— skills live in Git/FS; only pointers stored here

Hermes calls this instead of bloating MEMORY.md. Inject files stay tiny.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import httpx
import psycopg
from fastapi import FastAPI, HTTPException, Query
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

APP_NAME = "assistant-memory"
DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://hermes:hermes@postgres:5432/hermes_memory",
)
QDRANT_URL = os.environ.get("QDRANT_URL", "").rstrip("/")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "hermes_memory")
EMBED_URL = os.environ.get("EMBED_URL", "").rstrip("/")  # OpenAI-compat embeddings
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
EMBED_API_KEY = os.environ.get("EMBED_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
DEFAULT_BUDGET = int(os.environ.get("CONTEXT_BUDGET_TOKENS", "24000"))
WRITE_MODE = os.environ.get("MEMORY_WRITE_MODE", "live")  # live | staging | off
REDIS_URL = os.environ.get("REDIS_URL", "")
MEMORY_ASYNC = os.environ.get("MEMORY_ASYNC_INDEX", "1") == "1"
MEMORY_QUEUE = os.environ.get("MEMORY_JOB_QUEUE", "memory:jobs")
SESSION_URL = os.environ.get("SESSION_URL", "http://session:8107").rstrip("/")

MemoryType = Literal[
    "fact",
    "decision",
    "preference",
    "event",
    "task",
    "failure",
    "pointer",
]

def _timing_add(field: str, seconds: float, thread_id: Optional[str] = None) -> None:
    v = (os.environ.get("ZALO_TIMING_RECORD") or "1").strip().lower()
    if v in {"0", "false", "no", "off"} or seconds < 0.001:
        return
    try:
        with httpx.Client(timeout=1.5) as c:
            c.post(
                f"{SESSION_URL}/v1/timing/add",
                json={"field": field, "seconds": seconds, "thread_id": thread_id or ""},
            )
    except Exception:
        pass


app = FastAPI(title=APP_NAME, version="1.0.0")
pool: ConnectionPool | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _approx_tokens(text: str) -> int:
    # cheap estimator (~4 chars/token); good enough for budget gating
    return max(1, len(text) // 4)


SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
  id            TEXT PRIMARY KEY,
  type          TEXT NOT NULL,
  content       TEXT NOT NULL,
  importance    REAL NOT NULL DEFAULT 0.5,
  source        TEXT,
  session_id    TEXT,
  thread_id     TEXT,
  tags          TEXT[] NOT NULL DEFAULT '{}',
  metadata      JSONB NOT NULL DEFAULT '{}',
  valid_from    TIMESTAMPTZ,
  valid_until   TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  content_hash  TEXT NOT NULL,
  staged        BOOLEAN NOT NULL DEFAULT FALSE,
  active        BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS memories_type_idx ON memories (type) WHERE active;
CREATE INDEX IF NOT EXISTS memories_importance_idx ON memories (importance DESC) WHERE active;
CREATE INDEX IF NOT EXISTS memories_thread_idx ON memories (thread_id) WHERE active;
CREATE INDEX IF NOT EXISTS memories_created_idx ON memories (created_at DESC);
CREATE INDEX IF NOT EXISTS memories_fts_idx ON memories
  USING GIN (to_tsvector('simple', coalesce(content, '')));
CREATE INDEX IF NOT EXISTS memories_hash_idx ON memories (content_hash);

CREATE TABLE IF NOT EXISTS memory_audit (
  id          BIGSERIAL PRIMARY KEY,
  action      TEXT NOT NULL,
  memory_id   TEXT,
  detail      JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def _connect() -> ConnectionPool:
    return ConnectionPool(
        conninfo=DSN,
        min_size=1,
        max_size=8,
        check=ConnectionPool.check_connection,
        kwargs={"row_factory": dict_row, "autocommit": True},
    )


@app.on_event("startup")
def startup() -> None:
    global pool
    for attempt in range(30):
        try:
            pool = _connect()
            with pool.connection() as conn:
                conn.execute(SCHEMA)
            break
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)
    if MEMORY_ASYNC and REDIS_URL:
        import threading

        threading.Thread(target=_memory_job_worker, daemon=True).start()


def _memory_job_worker() -> None:
    """Background Redis consumer — embed/index off the HTTP remember path."""
    try:
        import redis as redis_lib
    except Exception:
        return
    while True:
        try:
            rd = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
            item = rd.blpop(MEMORY_QUEUE, timeout=5)
            if not item:
                continue
            job = json.loads(item[1])
            if job.get("op") == "index_memory":
                _index_memory(
                    job["id"],
                    job.get("content") or "",
                    job.get("type") or "fact",
                    float(job.get("importance") or 0.5),
                )
        except Exception:
            time.sleep(1)


@app.on_event("shutdown")
def shutdown() -> None:
    global pool
    if pool is not None:
        pool.close()
        pool = None


def db() -> ConnectionPool:
    if pool is None:
        raise HTTPException(503, "database not ready")
    return pool


class RememberReq(BaseModel):
    content: str = Field(min_length=3, max_length=4000)
    type: MemoryType = "fact"
    importance: float = Field(default=0.6, ge=0.0, le=1.0)
    source: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    force: bool = False  # bypass dedupe


class RecallReq(BaseModel):
    query: str = ""
    types: list[MemoryType] = Field(default_factory=list)
    thread_id: Optional[str] = None
    limit: int = Field(default=8, ge=1, le=50)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)


class ContextReq(BaseModel):
    text: str = ""
    has_media: bool = False
    thread_id: Optional[str] = None
    budget_tokens: int = Field(default=DEFAULT_BUDGET, ge=2000, le=200000)
    max_memories: int = Field(default=6, ge=0, le=20)


def _hash(content: str, typ: str) -> str:
    norm = re.sub(r"\s+", " ", content.strip().lower())
    return hashlib.sha256(f"{typ}|{norm}".encode()).hexdigest()[:32]


def _audit(conn: psycopg.Connection, action: str, memory_id: str | None, detail: dict) -> None:
    conn.execute(
        "INSERT INTO memory_audit (action, memory_id, detail) VALUES (%s, %s, %s::jsonb)",
        (action, memory_id, Json(detail)),
    )


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        with db().connection() as conn:
            conn.execute("SELECT 1")
        return {
            "ok": True,
            "service": APP_NAME,
            "write_mode": WRITE_MODE,
            "qdrant": bool(QDRANT_URL),
            "embed": bool(EMBED_URL),
        }
    except Exception as e:
        raise HTTPException(503, f"unhealthy: {e}") from e


@app.post("/v1/remember")
def remember(req: RememberReq) -> dict[str, Any]:
    if WRITE_MODE == "off":
        return {"success": False, "skipped": True, "reason": "MEMORY_WRITE_MODE=off"}

    # skip low-value noise
    low = req.content.strip().lower()
    if len(low) < 8 or low in {"ok", "thanks", "cảm ơn", "hi", "hello"}:
        return {"success": False, "skipped": True, "reason": "low_value"}

    staged = WRITE_MODE == "staging"
    content_hash = _hash(req.content, req.type)
    mid = f"mem_{uuid.uuid4().hex[:12]}"

    with db().connection() as conn:
        if not req.force:
            row = conn.execute(
                "SELECT id FROM memories WHERE content_hash=%s AND active LIMIT 1",
                (content_hash,),
            ).fetchone()
            if row:
                return {
                    "success": True,
                    "deduped": True,
                    "id": row["id"],
                    "staged": staged,
                }

        conn.execute(
            """
            INSERT INTO memories (
              id, type, content, importance, source, session_id, thread_id,
              tags, metadata, content_hash, staged, active, created_at, updated_at
            ) VALUES (
              %s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,TRUE,NOW(),NOW()
            )
            """,
            (
                mid,
                req.type,
                req.content.strip(),
                req.importance,
                req.source,
                req.session_id,
                req.thread_id,
                req.tags,
                Json(req.metadata),
                content_hash,
                staged,
            ),
        )
        _audit(conn, "remember", mid, {"type": req.type, "staged": staged})

    # Off user path: enqueue Redis index job (or best-effort sync fallback)
    queued = False
    if MEMORY_ASYNC and REDIS_URL:
        try:
            import redis as redis_lib

            rd = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
            rd.rpush(
                MEMORY_QUEUE,
                json.dumps(
                    {
                        "op": "index_memory",
                        "id": mid,
                        "content": req.content,
                        "type": req.type,
                        "importance": req.importance,
                    }
                ),
            )
            queued = True
        except Exception:
            queued = False
    if not queued:
        try:
            _index_memory(mid, req.content, req.type, req.importance)
        except Exception:
            pass

    return {"success": True, "id": mid, "staged": staged, "deduped": False, "async_index": queued}


@app.post("/v1/recall")
def recall(req: RecallReq) -> dict[str, Any]:
    clauses = ["active = TRUE", "staged = FALSE"]
    params: list[Any] = []
    if req.types:
        clauses.append("type = ANY(%s)")
        params.append(req.types)
    if req.thread_id:
        clauses.append("(thread_id = %s OR thread_id IS NULL)")
        params.append(req.thread_id)
    if req.min_importance > 0:
        clauses.append("importance >= %s")
        params.append(req.min_importance)

    q = req.query.strip()
    if q:
        clauses.append(
            "(to_tsvector('simple', content) @@ plainto_tsquery('simple', %s) OR content ILIKE %s)"
        )
        params.extend([q, f"%{q}%"])

    sql = f"""
      SELECT id, type, content, importance, source, tags, metadata, created_at
      FROM memories
      WHERE {' AND '.join(clauses)}
      ORDER BY importance DESC, created_at DESC
      LIMIT %s
    """
    params.append(req.limit)

    with db().connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    items = []
    for r in rows:
        items.append(
            {
                "id": r["id"],
                "type": r["type"],
                "content": r["content"],
                "importance": float(r["importance"]),
                "source": r["source"],
                "tags": r["tags"] or [],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
        )
    return {"success": True, "count": len(items), "items": items}


@app.get("/v1/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(8, ge=1, le=50),
) -> dict[str, Any]:
    return recall(RecallReq(query=q, limit=limit))


MODE_SKILLS = {
    "chat": ["common-rules", "context-budget", "memory-hygiene", "chat", "outbound-media"],
    "research": ["common-rules", "context-budget", "memory-hygiene", "research"],
    "upload": ["common-rules", "context-budget", "memory-hygiene", "upload"],
    "code": ["common-rules", "context-budget", "memory-hygiene", "code"],
    "content-policy": ["content-policy", "common-rules"],
    "no-outbound-doc": ["no-outbound-doc", "common-rules"],
    "file-gen": ["file-gen", "common-rules"],
    "no-av-watch": ["no-av-watch", "common-rules"],
    "outbound-media": ["common-rules", "outbound-media"],
    "video-summary": ["common-rules", "context-budget", "video-summary"],
}


def _has_social_video_url(t: str) -> bool:
    return bool(
        re.search(
            r"youtube\.com|youtu\.be|tiktok\.com|vm\.tiktok\.com|douyin\.com|"
            r"facebook\.com|fb\.watch|fb\.com/watch",
            t,
        )
    )


def _has_av_url(t: str) -> bool:
    return _has_social_video_url(t) or bool(
        re.search(r"spotify\.com|soundcloud\.com", t)
    )


def _wants_video_summary(t: str) -> bool:
    if not _has_social_video_url(t):
        return False
    if re.search(
        r"tr[ií]ch\s*l[oờ]i|lyrics|transcript|ph[uụ]\s*[đd][eề]|t[oó]m\s*t[aắ]t|summary|summarize|"
        r"n[oộ]i dung|n[oó]i g[iì]|b[ih]t g[iì]|caption|subtitles?",
        t,
    ):
        return True
    # Link-only paste (no explicit watch/listen) → assume summary intent
    return not re.search(r"\b(xem|nghe|coi|watch|listen|play|ph[aá]t)\b", t)


def _wants_av_watch_only(t: str) -> bool:
    if re.search(
        r"\b(xem|nghe|coi|watch|listen|play|ph[aá]t)\b.*(youtube|tiktok|facebook|fb\.|mp3|mp4|livestream|nh[aạ]c|live)|"
        r"(youtube|tiktok|facebook|fb\.|mp3|mp4|livestream|nh[aạ]c|live).*\b(xem|nghe|coi|watch|listen|play|ph[aá]t)\b",
        t,
    ):
        return not re.search(
            r"tr[ií]ch\s*l[oờ]i|lyrics|transcript|ph[uụ]\s*[đd][eề]|t[oó]m\s*t[aắ]t|summary|summarize",
            t,
        )
    return bool(re.search(r"\.(mp3|mp4|mkv|webm|mov|avi|wav|flac|m4a)\b", t))


def _infer_mode(text: str, has_media: bool) -> str:
    t = text.lower()
    if re.search(
        r"chi[eế]n tranh|nga|ukraine|russia|ch[ií]nh tr[iị]|b[aầ]u c[uử]|ch[uủ]ng t[oộ]c|gi[oớ]i t[ií]nh|hate",
        t,
    ):
        return "content-policy"
    if has_media and not re.search(
        r"t[aạ]o\s*(file|excel|word|pdf|b[aả]ng)|xu[aấ]t\s*(file|excel|xlsx)",
        t,
    ):
        return "upload"
    if re.search(
        r"t[aạ]o\s*(file|excel|word|pdf|b[aả]ng)|xu[aấ]t\s*(file|excel|xlsx|csv|b[aả]ng)|"
        r"l[aà]m\s*(file|b[aả]ng)",
        t,
    ):
        if re.search(r"\.(mp3|mp4|wav|flac|mov|mkv|webm)\b|nh[aạ]c|video\s*clip", t):
            return "no-av-watch"
        return "file-gen"
    if re.search(
        r"g[uử]i pdf|upload file|b[aằ]ng ch[uứ]ng|prove|manual", t
    ) and not re.search(
        r"t[aạ]o|xu[aấ]t|l[aà]m file", t
    ):
        return "no-outbound-doc"
    if re.search(
        r"(t[aạ]o|v[eẽ]|gen(erate)?).{0,80}(h[iì]nh|ảnh|anh|jpeg|jpg|png|poster)",
        t,
    ) and not re.search(r"\.(xlsx|docx|pdf|csv|txt)\b", t):
        return "outbound-media"
    if _wants_video_summary(t):
        return "video-summary"
    if _wants_av_watch_only(t) or (_has_av_url(t) and not _has_social_video_url(t)):
        return "no-av-watch"
    if has_media or re.search(r"ph[aâ]n t[ií]ch|ocr|[đd][aâ]y l[aà] g[iì]", t):
        return "upload"
    if re.search(r"gi[aá]|tin|search|http|t[oó]m t[aắ]t", t):
        return "research"
    if re.search(r"code|bug|stacktrace|refactor", t):
        return "code"
    return "chat"


@app.post("/v1/context")
def assemble_context(req: ContextReq) -> dict[str, Any]:
    """Context Manager gate: mode + few skills + top memories within token budget."""
    t0 = time.time()
    try:
        mode = _infer_mode(req.text, req.has_media)
        skills = MODE_SKILLS.get(mode, MODE_SKILLS["chat"])

        mem_budget = min(req.budget_tokens // 4, 4000)  # ~25% for memories max
        recalled = recall(
            RecallReq(query=req.text, thread_id=req.thread_id, limit=req.max_memories)
        )["items"]

        selected: list[dict[str, Any]] = []
        used = 0
        for m in recalled:
            cost = _approx_tokens(m["content"])
            if used + cost > mem_budget:
                break
            selected.append(m)
            used += cost

        system_hints = [
            "CONTEXT MANAGER: use only the skills and memories below for this turn.",
            f"MODE={mode}",
            f"SKILLS={', '.join(skills)}",
            f"BUDGET_TOKENS={req.budget_tokens} (keep total prompt well under this).",
            "Do not dump docs into MEMORY.md; call memory manager for durable facts.",
            "One short Zalo reply. Do not invent a timing footer.",
        ]
        if selected:
            system_hints.append("RECALLED_MEMORIES:")
            for m in selected:
                system_hints.append(f"- [{m['type']}|{m['importance']:.2f}] {m['content']}")

        hint_text = "\n".join(system_hints)
        return {
            "success": True,
            "mode": mode,
            "skills": skills,
            "memories": selected,
            "budget_tokens": req.budget_tokens,
            "memory_tokens_est": used,
            "hints_tokens_est": _approx_tokens(hint_text),
            "system_hints": hint_text,
        }
    finally:
        _timing_add("workflow_s", time.time() - t0, getattr(req, "thread_id", None))


@app.post("/v1/promote/{memory_id}")
def promote(memory_id: str) -> dict[str, Any]:
    with db().connection() as conn:
        cur = conn.execute(
            "UPDATE memories SET staged=FALSE, updated_at=NOW() WHERE id=%s RETURNING id",
            (memory_id,),
        ).fetchone()
        if not cur:
            raise HTTPException(404, "not found")
        _audit(conn, "promote", memory_id, {})
    return {"success": True, "id": memory_id}


@app.delete("/v1/memory/{memory_id}")
def deactivate(memory_id: str) -> dict[str, Any]:
    with db().connection() as conn:
        cur = conn.execute(
            "UPDATE memories SET active=FALSE, updated_at=NOW() WHERE id=%s RETURNING id",
            (memory_id,),
        ).fetchone()
        if not cur:
            raise HTTPException(404, "not found")
        _audit(conn, "deactivate", memory_id, {})
    return {"success": True, "id": memory_id}


@app.get("/v1/stats")
def stats() -> dict[str, Any]:
    with db().connection() as conn:
        rows = conn.execute(
            """
            SELECT type, COUNT(*) AS n
            FROM memories WHERE active AND NOT staged
            GROUP BY type ORDER BY n DESC
            """
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM memories WHERE active AND NOT staged"
        ).fetchone()["n"]
        staged = conn.execute(
            "SELECT COUNT(*) AS n FROM memories WHERE active AND staged"
        ).fetchone()["n"]
    return {
        "active": total,
        "staged": staged,
        "by_type": {r["type"]: r["n"] for r in rows},
        "write_mode": WRITE_MODE,
    }


def _index_memory(mid: str, content: str, typ: str, importance: float) -> None:
    if not QDRANT_URL or not EMBED_URL:
        return
    vec = _embed(content)
    if not vec:
        return
    httpx.put(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points?wait=true",
        json={
            "points": [
                {
                    "id": abs(hash(mid)) % (10**12),
                    "vector": vec,
                    "payload": {
                        "memory_id": mid,
                        "type": typ,
                        "importance": importance,
                        "content": content[:500],
                    },
                }
            ]
        },
        timeout=10.0,
    ).raise_for_status()


def _embed(text: str) -> list[float] | None:
    if not EMBED_URL:
        return None
    headers = {"Authorization": f"Bearer {EMBED_API_KEY}"} if EMBED_API_KEY else {}
    r = httpx.post(
        f"{EMBED_URL}/embeddings",
        headers=headers,
        json={"model": EMBED_MODEL, "input": text[:8000]},
        timeout=30.0,
    )
    if r.status_code >= 400:
        return None
    data = r.json().get("data") or []
    if not data:
        return None
    return data[0].get("embedding")
