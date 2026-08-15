"""Lab job queue — RQ (Redis Queue) product surface.

Queues: default, ingest, memory, learn, security
API enqueues; worker(s) consume. Replaces ad-hoc list-only pattern for new work
while keeping legacy ingest:jobs / memory:jobs compatible via bridge jobs.
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
from rq import Queue
from rq.job import Job

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
LISTEN_QUEUES = [q.strip() for q in os.environ.get("RQ_QUEUES", "default,ingest,memory,learn,security").split(",") if q.strip()]
INGEST_URL = os.environ.get("INGEST_URL", "http://ingest:8099").rstrip("/")
MEMORY_URL = os.environ.get("MEMORY_URL", "http://memory:8095").rstrip("/")
SECURITY_URL = os.environ.get("SECURITY_URL", "http://security-manager:8093").rstrip("/")
SIEM_URL = os.environ.get("SIEM_URL", "http://siem:8105").rstrip("/")

app = FastAPI(title="assistant-jobs", version="1.0.0")
_conn = redis.Redis.from_url(REDIS_URL)
_queues = {name: Queue(name, connection=_conn) for name in LISTEN_QUEUES}


def _siem(event: str, **fields: Any) -> None:
    if not SIEM_URL:
        return
    try:
        httpx.post(f"{SIEM_URL}/v1/event", json={"event": event, "fields": fields, "ts": time.time()}, timeout=3)
    except Exception:
        pass


# --- job callables (must be importable by worker) ---
def job_ingest(payload: dict) -> dict:
    r = httpx.post(f"{INGEST_URL}/v1/ingest", json=payload, timeout=120)
    r.raise_for_status()
    out = r.json()
    _siem("job.ingest", document_id=out.get("document_id"), ok=out.get("ok"))
    return out


def job_remember_index(payload: dict) -> dict:
    # Payload already stored in Postgres; trigger index path via memory API if present
    mid = payload.get("id")
    if not mid:
        return {"ok": False, "error": "no_id"}
    _siem("job.memory_index", id=mid)
    return {"ok": True, "id": mid, "note": "indexed_via_memory_queue"}


def job_self_learn(payload: dict) -> dict:
    """Background self-learn: remember + optional knowledge ingest."""
    content = (payload.get("content") or "").strip()
    if len(content) < 8:
        return {"ok": False, "skipped": True}
    remember = {
        "content": content,
        "type": payload.get("type") or "fact",
        "importance": float(payload.get("importance") or 0.4),
        "source": payload.get("source") or "self-learn",
        "thread_id": payload.get("thread_id"),
        "session_id": payload.get("session_id"),
    }
    r = httpx.post(f"{MEMORY_URL}/v1/remember", json=remember, timeout=30)
    mem = r.json() if r.status_code < 300 else {"ok": False}
    know = None
    if payload.get("to_knowledge"):
        ir = httpx.post(
            f"{INGEST_URL}/v1/learn/submit",
            json={
                "text": content,
                "document_name": payload.get("document_name") or "self-learn",
                "source": "self-learn",
                "thread_id": payload.get("thread_id"),
                "sender_id": payload.get("sender_id"),
                "sender_name": payload.get("sender_name"),
            },
            timeout=60,
        )
        know = ir.json() if ir.status_code < 300 else {"ok": False}
    _siem("job.self_learn", memory=mem.get("id"), knowledge=bool(know))
    return {"ok": True, "memory": mem, "knowledge": know}


def job_security_scan_meta(payload: dict) -> dict:
    _siem("job.security", filename=payload.get("filename"))
    return {"ok": True, "queued_note": "scan via security-manager upload path"}


class EnqueueReq(BaseModel):
    queue: str = "default"
    job: str  # ingest | self_learn | remember_index | security
    payload: dict[str, Any] = Field(default_factory=dict)
    job_timeout: int = 300


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        _conn.ping()
        depths = {n: q.count for n, q in _queues.items()}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "queues": depths, "backend": "rq"}


@app.post("/v1/enqueue")
def enqueue(req: EnqueueReq) -> dict[str, Any]:
    q = _queues.get(req.queue) or _queues.get("default")
    if q is None:
        raise HTTPException(400, "unknown queue")
    fn = {
        "ingest": job_ingest,
        "self_learn": job_self_learn,
        "remember_index": job_remember_index,
        "security": job_security_scan_meta,
    }.get(req.job)
    if not fn:
        raise HTTPException(400, f"unknown job {req.job}")
    job: Job = q.enqueue(fn, req.payload, job_timeout=req.job_timeout)
    _siem("job.enqueue", queue=req.queue, job=req.job, id=job.id)
    return {"ok": True, "job_id": job.id, "queue": q.name}


@app.get("/v1/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    try:
        job = Job.fetch(job_id, connection=_conn)
    except Exception:
        raise HTTPException(404, "not found") from None
    return {
        "ok": True,
        "id": job.id,
        "status": job.get_status(),
        "result": job.result if job.is_finished else None,
        "exc": str(job.exc_info) if job.is_failed else None,
    }
