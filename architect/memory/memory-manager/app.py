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
import time
import uuid
from datetime import date, datetime, timezone
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
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "conversational_memory")
EMBED_URL = os.environ.get("EMBED_URL", "").rstrip("/")  # OpenAI-compat embeddings
EMBED_MODEL = os.environ.get("EMBED_MODEL", "embedding")
EMBED_API_KEY = os.environ.get("EMBED_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
DEFAULT_BUDGET = int(os.environ.get("CONTEXT_BUDGET_TOKENS", "24000"))
WRITE_MODE = os.environ.get("MEMORY_WRITE_MODE", "live")  # live | staging | off
REDIS_URL = os.environ.get("REDIS_URL", "")
MEMORY_ASYNC = os.environ.get("MEMORY_ASYNC_INDEX", "1") == "1"
MEMORY_QUEUE = os.environ.get("MEMORY_JOB_QUEUE", "memory:jobs")
SESSION_URL = os.environ.get("SESSION_URL", "http://session:8107").rstrip("/")
STAGED_RETENTION_DAYS = max(
    1, min(int(os.environ.get("MEMORY_STAGED_RETENTION_DAYS", "7")), 3650)
)

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
    v = (os.environ.get("MESSAGE_TIMING_RECORD") or "1").strip().lower()
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
CREATE INDEX IF NOT EXISTS memories_session_idx ON memories (session_id) WHERE active;
CREATE INDEX IF NOT EXISTS memories_thread_session_created_idx ON memories
  (thread_id, session_id, created_at DESC) WHERE active AND NOT staged;
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

CREATE TABLE IF NOT EXISTS notes (
  id            TEXT PRIMARY KEY,
  scope_id      TEXT NOT NULL,
  thread_id     TEXT,
  thread_type   TEXT,
  owner_id      TEXT,
  title         TEXT,
  content       TEXT NOT NULL,
  note_date     DATE,
  tags          TEXT[] NOT NULL DEFAULT '{}',
  metadata      JSONB NOT NULL DEFAULT '{}',
  note_hash     TEXT NOT NULL,
  version       INTEGER NOT NULL DEFAULT 1,
  active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE notes ADD COLUMN IF NOT EXISTS title TEXT;
CREATE INDEX IF NOT EXISTS notes_scope_date_idx
  ON notes (scope_id, note_date, updated_at DESC) WHERE active;
CREATE INDEX IF NOT EXISTS notes_scope_updated_idx
  ON notes (scope_id, updated_at DESC) WHERE active;
CREATE INDEX IF NOT EXISTS notes_fts_idx ON notes
  USING GIN (to_tsvector('simple', coalesce(content, ''))) WHERE active;
CREATE INDEX IF NOT EXISTS notes_title_content_fts_idx ON notes
  USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))) WHERE active;
CREATE UNIQUE INDEX IF NOT EXISTS notes_dedupe_idx ON notes
  (scope_id, note_hash, coalesce(note_date, DATE '0001-01-01')) WHERE active;

CREATE TABLE IF NOT EXISTS note_audit (
  id          BIGSERIAL PRIMARY KEY,
  action      TEXT NOT NULL,
  note_id     TEXT,
  scope_id    TEXT NOT NULL,
  version     INTEGER,
  detail      JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS note_audit_note_idx
  ON note_audit (note_id, created_at DESC);
"""


def _connect() -> ConnectionPool:
    return ConnectionPool(
        conninfo=DSN,
        min_size=1,
        max_size=8,
        check=ConnectionPool.check_connection,
        kwargs={"row_factory": dict_row, "autocommit": True},
    )



def _ensure_qdrant_collection(dim: int | None = None) -> None:
    """Create QDRANT_COLLECTION when missing (Grafana expects conversational_memory)."""
    if not QDRANT_URL or not QDRANT_COLLECTION:
        return
    size = dim
    if size is None:
        try:
            size = int(os.environ.get("QDRANT_VECTOR_SIZE", "0") or "0")
        except ValueError:
            size = 0
    if not size and EMBED_URL:
        vec = _embed("collection-bootstrap")
        if vec:
            size = len(vec)
    if not size:
        size = 384
    try:
        r = httpx.get(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}", timeout=15.0)
        if r.status_code == 200:
            return
        httpx.put(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}",
            json={"vectors": {"size": int(size), "distance": "Cosine"}},
            timeout=15.0,
        )
    except Exception:
        pass


@app.on_event("startup")
def startup() -> None:
    global pool
    for attempt in range(30):
        try:
            pool = _connect()
            with pool.connection() as conn:
                conn.execute(SCHEMA)
            _ensure_qdrant_collection()
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
    session_id: Optional[str] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    limit: int = Field(default=8, ge=1, le=50)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)


class ContextReq(BaseModel):
    text: str = ""
    has_media: bool = False
    thread_id: Optional[str] = None
    budget_tokens: int = Field(default=DEFAULT_BUDGET, ge=2000, le=200000)
    max_memories: int = Field(default=6, ge=0, le=20)
    task_hint: Optional[str] = None


class NoteCreateReq(BaseModel):
    scope_id: str = Field(min_length=3, max_length=256)
    title: Optional[str] = Field(default=None, max_length=240)
    content: str = Field(min_length=3, max_length=8000)
    note_date: Optional[str] = None
    thread_id: Optional[str] = None
    thread_type: Optional[str] = None
    owner_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NoteQueryReq(BaseModel):
    scope_id: str = Field(min_length=3, max_length=256)
    id: Optional[str] = Field(default=None, max_length=96)
    query: str = Field(default="", max_length=1000)
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=1000)


class NoteUpdateReq(BaseModel):
    scope_id: str = Field(min_length=3, max_length=256)
    title: Optional[str] = Field(default=None, max_length=240)
    content: Optional[str] = Field(default=None, min_length=3, max_length=8000)
    note_date: Optional[str] = None
    clear_date: bool = False
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


def _hash(content: str, typ: str) -> str:
    norm = " ".join(content.strip().lower().split())
    return hashlib.sha256(f"{typ}|{norm}".encode()).hexdigest()[:32]


def _parse_note_date(value: str | None, field: str) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(422, f"{field} must be YYYY-MM-DD") from exc


def _note_hash(content: str) -> str:
    normalized = " ".join(str(content or "").strip().casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _note_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row.get("title"),
        "content": row["content"],
        "note_date": row["note_date"].isoformat() if row.get("note_date") else None,
        "tags": list(row.get("tags") or []),
        "metadata": dict(row.get("metadata") or {}),
        "version": int(row.get("version") or 1),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def _note_audit(
    conn: psycopg.Connection,
    action: str,
    note_id: str,
    scope_id: str,
    version: int,
    detail: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO note_audit (action, note_id, scope_id, version, detail)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (action, note_id, scope_id, version, Json(detail)),
    )


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


@app.post("/v1/notes")
def create_note(req: NoteCreateReq) -> dict[str, Any]:
    """Persist one scoped, optionally dated note with an immutable audit row."""
    content = req.content.strip()
    title = str(req.title or "").strip()[:240] or None
    note_date = _parse_note_date(req.note_date, "note_date")
    note_hash = _note_hash(content)
    note_id = f"note_{uuid.uuid4().hex[:12]}"
    tags = list(dict.fromkeys(str(tag).strip()[:64] for tag in req.tags if str(tag).strip()))[:24]
    with db().connection() as conn:
        existing = conn.execute(
            """
            SELECT * FROM notes
            WHERE scope_id=%s AND note_hash=%s
              AND note_date IS NOT DISTINCT FROM %s AND active
            LIMIT 1
            """,
            (req.scope_id, note_hash, note_date),
        ).fetchone()
        if existing:
            if title and not str(existing.get("title") or "").strip():
                version = int(existing.get("version") or 1) + 1
                existing = conn.execute(
                    """
                    UPDATE notes SET title=%s, version=%s, updated_at=NOW()
                    WHERE id=%s AND scope_id=%s AND active
                    RETURNING *
                    """,
                    (title, version, existing["id"], req.scope_id),
                ).fetchone()
                _note_audit(
                    conn,
                    "title_backfill",
                    existing["id"],
                    req.scope_id,
                    version,
                    {"source": "deduped_create"},
                )
            return {"success": True, "deduped": True, "note": _note_row(existing)}
        row = conn.execute(
            """
            INSERT INTO notes (
              id, scope_id, thread_id, thread_type, owner_id, title, content,
              note_date, tags, metadata, note_hash
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            RETURNING *
            """,
            (
                note_id,
                req.scope_id,
                req.thread_id,
                req.thread_type,
                req.owner_id,
                title,
                content,
                note_date,
                tags,
                Json(req.metadata),
                note_hash,
            ),
        ).fetchone()
        _note_audit(conn, "create", note_id, req.scope_id, 1, {"note_date": req.note_date})
    return {"success": True, "deduped": False, "note": _note_row(row)}


@app.post("/v1/notes/query")
def query_notes(req: NoteQueryReq) -> dict[str, Any]:
    """Fast scope/date lookup with optional full-text and tag filters."""
    date_from = _parse_note_date(req.date_from, "date_from")
    date_to = _parse_note_date(req.date_to, "date_to")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must not be after date_to")
    clauses = ["scope_id=%s", "active"]
    params: list[Any] = [req.scope_id]
    if req.id:
        clauses.append("id=%s")
        params.append(req.id.strip())
    if date_from:
        clauses.append("note_date >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("note_date <= %s")
        params.append(date_to)
    # Preserve the strict scope/date boundary separately. Classifier-produced
    # semantic tags may differ by language from the tags stored earlier; they
    # must not hide an otherwise correct dated note.
    date_clauses = list(clauses)
    date_params = list(params)
    if req.tags:
        clauses.append("tags && %s")
        params.append(list(dict.fromkeys(req.tags))[:24])
    query = req.query.strip()
    if query:
        clauses.append(
            "(to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')) @@ plainto_tsquery('simple', %s) OR title ILIKE %s OR content ILIKE %s)"
        )
        params.extend([query, f"%{query}%", f"%{query}%"])
    params.append(req.limit)
    sql = f"""
      SELECT * FROM notes
      WHERE {' AND '.join(clauses)}
      ORDER BY updated_at DESC, note_date DESC NULLS LAST
      LIMIT %s
    """
    fallback_used = False
    with db().connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        # A narrow wording filter must not hide dated plans. Return the scoped
        # date window as fallback candidates so the caller can answer naturally.
        # Relax both query wording and semantic tags, never scope/date bounds.
        if query and not rows and (date_from or date_to):
            fallback_clauses = date_clauses
            fallback_params = date_params + [req.limit]
            fallback_sql = f"""
              SELECT * FROM notes
              WHERE {' AND '.join(fallback_clauses)}
              ORDER BY updated_at DESC, note_date DESC NULLS LAST
              LIMIT %s
            """
            rows = conn.execute(fallback_sql, fallback_params).fetchall()
            fallback_used = bool(rows)
    return {
        "success": True,
        "count": len(rows),
        "query_fallback": fallback_used,
        "items": [_note_row(row) for row in rows],
    }


@app.patch("/v1/notes/{note_id}")
def update_note(note_id: str, req: NoteUpdateReq) -> dict[str, Any]:
    note_date = None if req.clear_date else _parse_note_date(req.note_date, "note_date")
    with db().connection() as conn:
        current = conn.execute(
            "SELECT * FROM notes WHERE id=%s AND scope_id=%s AND active",
            (note_id, req.scope_id),
        ).fetchone()
        if not current:
            raise HTTPException(404, "note not found")
        content = req.content.strip() if req.content is not None else current["content"]
        title = (
            str(req.title or "").strip()[:240] or None
            if req.title is not None
            else current.get("title")
        )
        effective_date = (
            None
            if req.clear_date
            else note_date if req.note_date is not None else current["note_date"]
        )
        tags = (
            list(dict.fromkeys(str(tag).strip()[:64] for tag in req.tags if str(tag).strip()))[:24]
            if req.tags is not None
            else current["tags"]
        )
        metadata = req.metadata if req.metadata is not None else current["metadata"]
        version = int(current["version"] or 1) + 1
        row = conn.execute(
            """
            UPDATE notes SET title=%s, content=%s, note_date=%s, tags=%s, metadata=%s::jsonb,
              note_hash=%s, version=%s, updated_at=NOW()
            WHERE id=%s AND scope_id=%s AND active
            RETURNING *
            """,
            (
                title,
                content,
                effective_date,
                tags,
                Json(metadata),
                _note_hash(content),
                version,
                note_id,
                req.scope_id,
            ),
        ).fetchone()
        _note_audit(conn, "update", note_id, req.scope_id, version, {"previous": _note_row(current)})
    return {"success": True, "note": _note_row(row)}


@app.delete("/v1/notes/{note_id}")
def delete_note(note_id: str, scope_id: str = Query(..., min_length=3)) -> dict[str, Any]:
    with db().connection() as conn:
        current = conn.execute(
            "SELECT * FROM notes WHERE id=%s AND scope_id=%s AND active",
            (note_id, scope_id),
        ).fetchone()
        if not current:
            raise HTTPException(404, "note not found")
        version = int(current["version"] or 1) + 1
        conn.execute(
            "UPDATE notes SET active=FALSE, version=%s, updated_at=NOW() WHERE id=%s",
            (version, note_id),
        )
        _note_audit(conn, "delete", note_id, scope_id, version, {"previous": _note_row(current)})
    return {"success": True, "id": note_id, "version": version}


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
    if req.session_id:
        clauses.append("session_id = %s")
        params.append(req.session_id)
    if req.created_from:
        clauses.append("created_at >= %s")
        params.append(req.created_from)
    if req.created_to:
        clauses.append("created_at <= %s")
        params.append(req.created_to)
    if req.min_importance > 0:
        clauses.append("importance >= %s")
        params.append(req.min_importance)

    q = req.query.strip()
    base_clauses = list(clauses)
    base_params = list(params)
    if q:
        clauses.append(
            "to_tsvector('simple', coalesce(content, '')) @@ plainto_tsquery('simple', %s)"
        )
        params.append(q)

    sql = f"""
      SELECT id, type, content, importance, source, session_id, tags, metadata, created_at
      FROM memories
      WHERE {' AND '.join(clauses)}
      ORDER BY importance DESC, created_at DESC
      LIMIT %s
    """
    params.append(req.limit)

    with db().connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        if q and not rows:
            fallback_params = base_params + [f"%{q}%", req.limit]
            fallback_sql = f"""
              SELECT id, type, content, importance, source, session_id, tags, metadata, created_at
              FROM memories
              WHERE {' AND '.join(base_clauses)} AND content ILIKE %s
              ORDER BY importance DESC, created_at DESC
              LIMIT %s
            """
            rows = conn.execute(fallback_sql, fallback_params).fetchall()

    items = []
    for r in rows:
        items.append(
            {
                "id": r["id"],
                "type": r["type"],
                "content": r["content"],
                "importance": float(r["importance"]),
                "source": r["source"],
                "session_id": r["session_id"],
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


_HINT_MODE = {
    "file": "file-gen",
    "coding": "code",
    "search": "research",
    "knowledge": "research",
    "tool": "outbound-media",
    "schedule": "chat",
    "normal": "chat",
    "unknown": "chat",
}
_SOCIAL_HOSTS = (
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "vm.tiktok.com",
    "douyin.com",
    "facebook.com",
    "fb.watch",
    "fb.com/watch",
)
_AV_HOSTS = _SOCIAL_HOSTS + ("spotify.com", "soundcloud.com")


def _has_social_video_url(t: str) -> bool:
    low = (t or "").lower()
    return any(h in low for h in _SOCIAL_HOSTS)


def _has_av_url(t: str) -> bool:
    low = (t or "").lower()
    return any(h in low for h in _AV_HOSTS)


def _infer_mode(text: str, has_media: bool, task_hint: str = "") -> str:
    hint = (task_hint or "").strip().lower()
    if hint in _HINT_MODE:
        return _HINT_MODE[hint]
    if has_media:
        return "upload"
    if _has_social_video_url(text):
        return "video-summary"
    if _has_av_url(text):
        return "no-av-watch"
    return "chat"


@app.post("/v1/context")
def assemble_context(req: ContextReq) -> dict[str, Any]:
    """Context Manager gate: mode + few skills + top memories within token budget."""
    t0 = time.time()
    try:
        mode = _infer_mode(req.text, req.has_media, req.task_hint or "")
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
            "One short messaging reply. Do not invent a timing footer.",
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


@app.post("/v1/compact")
def compact(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    """Housekeep memory index via the embedding combo (run.sh compact / timer).

    Re-embeds recent active rows into Qdrant when EMBED_URL is configured.
    Soft-deactivates very old staged rows. Never raises on empty DB.
    """
    reindexed = 0
    deactivated = 0
    embed_ok = False
    embed_err = ""
    model = (EMBED_MODEL or "embedding").strip() or "embedding"
    with db().connection() as conn:
        # Drop stale staged drafts (keep live memories).
        try:
            cur = conn.execute(
                """
                UPDATE memories
                SET active = false
                WHERE staged AND active
                  AND created_at < NOW() - (%s * INTERVAL '1 day')
                """,
                (STAGED_RETENTION_DAYS,),
            )
            deactivated = int(cur.rowcount or 0)
            conn.commit()
        except Exception as e:  # noqa: BLE001
            embed_err = f"staged_cleanup:{type(e).__name__}"
            try:
                conn.rollback()
            except Exception:
                pass
        rows = conn.execute(
            """
            SELECT id, content, type, importance
            FROM memories
            WHERE active AND NOT staged
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT %s
            """,
            (int(limit),),
        ).fetchall()
    if not EMBED_URL:
        return {
            "ok": True,
            "reindexed": 0,
            "deactivated_staged": deactivated,
            "embed_model": model,
            "embed": False,
            "note": "EMBED_URL unset",
        }
    for row in rows:
        try:
            _index_memory(
                str(row["id"]),
                str(row.get("content") or ""),
                str(row.get("type") or "fact"),
                float(row.get("importance") or 0.5),
            )
            reindexed += 1
            embed_ok = True
        except Exception as e:  # noqa: BLE001
            embed_err = type(e).__name__
            break
    return {
        "ok": True,
        "reindexed": reindexed,
        "deactivated_staged": deactivated,
        "embed_model": model,
        "embed": embed_ok or reindexed > 0,
        "error": embed_err or None,
    }


def _index_memory(mid: str, content: str, typ: str, importance: float) -> None:
    if not QDRANT_URL or not EMBED_URL:
        return
    vec = _embed(content)
    if not vec:
        return
    _ensure_qdrant_collection(dim=len(vec))
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
    mid = (EMBED_MODEL or "embedding").strip() or "embedding"
    r = httpx.post(
        f"{EMBED_URL}/embeddings",
        headers=headers,
        json={"model": mid, "input": text[:8000]},
        timeout=30.0,
    )
    if r.status_code >= 400:
        return None
    data = r.json().get("data") or []
    if not data:
        return None
    return data[0].get("embedding")
