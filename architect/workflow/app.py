"""Generic workflow API — Postgres canonical state, Valkey delivery."""
from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from manager import WorkflowManager
from plan import extract_cadence, extract_cron_expr, plan_instructions
from store import MemoryStore

WORKER_ID = os.environ.get("HOSTNAME") or "workflow-api"
HERMES_API_URL = (
    os.environ.get("HERMES_API_URL") or "http://hermes:8642/v1/chat/completions"
).rstrip("/")
HERMES_API_KEY = (os.environ.get("HERMES_API_KEY") or "").strip()
HERMES_WORKFLOW_TIMEOUT_S = float(os.environ.get("HERMES_WORKFLOW_TIMEOUT_S") or "90")
DEFAULT_TZ = os.environ.get("TZ") or "Asia/Ho_Chi_Minh"


def _parse_next_run(raw: str | None):
    text = (raw or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _manager() -> WorkflowManager:
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if dsn:
        from postgres import PostgresStore

        return WorkflowManager(PostgresStore(dsn))
    return WorkflowManager(MemoryStore())


mgr = _manager()


def _auth_headers(api_key: str) -> dict[str, str]:
    key = (api_key or HERMES_API_KEY).strip()
    if not key:
        return {"Content-Type": "application/json"}
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }


def _extract_text(data: Any) -> str:
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, list):
        parts: list[str] = []
        for item in data:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _result_text(result: dict[str, Any] | None) -> str:
    data = result or {}
    for key in ("text", "content", "output_text"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    choices = data.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            msg = choice.get("message")
            if isinstance(msg, dict):
                text = _extract_text(msg.get("content"))
                if text:
                    return text
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            text = _extract_text(item.get("content"))
            if text:
                return text
    return ""


def _run_hermes_job(job: dict[str, Any]) -> dict[str, Any]:
    ctx = job.get("context") if isinstance(job.get("context"), dict) else {}
    instruction = str(job.get("instruction") or "").strip()
    if not instruction:
        raise ValueError("missing instruction")
    api_url = str(ctx.get("api_url") or HERMES_API_URL).strip() or HERMES_API_URL
    api_key = str(ctx.get("api_key") or HERMES_API_KEY).strip()
    model = str(ctx.get("model") or "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": instruction}],
    }
    started = time.time()
    with httpx.Client(timeout=HERMES_WORKFLOW_TIMEOUT_S) as client:
        resp = client.post(api_url, headers=_auth_headers(api_key), json=payload)
        resp.raise_for_status()
        data = resp.json()
    return {
        "ok": True,
        "text": _result_text(data),
        "raw": data,
        "elapsed_ms": int((time.time() - started) * 1000),
    }


async def _loops() -> None:
    while True:
        try:
            mgr.recover_stale()
            mgr.fire_due_schedules()
            mgr.dispatch_outbox()
            for _ in range(8):
                job = mgr.claim(WORKER_ID, execute="record_only")
                if not job:
                    break
                mgr.complete(job["id"], {"ok": True, "execute": "record_only"})
            for _ in range(4):
                job = mgr.claim(WORKER_ID, execute="hermes_http")
                if not job:
                    break
                try:
                    mgr.complete(job["id"], _run_hermes_job(job))
                except Exception as e:
                    mgr.fail(job["id"], type(e).__name__)
        except Exception as e:
            print(f"[workflow] loop error {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(2.0)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_loops())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="assistant-workflow", version="1.0.0", lifespan=lifespan)


class CreateReq(BaseModel):
    instructions: list[str] = Field(default_factory=list)
    text: str = ""
    origin: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    sequential: bool = True
    idempotency_prefix: Optional[str] = None
    wrap: bool = True


class WaitReq(BaseModel):
    timeout_s: float = 90.0


class ScheduleReq(BaseModel):
    id: Optional[str] = None
    name: str = ""
    cron_expr: str = ""
    time: str = ""
    timezone: str = "Asia/Ho_Chi_Minh"
    text: str = ""
    origin: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    next_run_at: Optional[str] = None
    cadence: str = ""


class CompleteReq(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)


class FailReq(BaseModel):
    error: str = "failed"


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "workflow"}


@app.post("/v1/workflows")
def create_wf(req: CreateReq) -> dict[str, Any]:
    texts = [t for t in req.instructions if str(t).strip()]
    if not texts and req.text.strip():
        texts = plan_instructions(req.text)
    if not texts:
        raise HTTPException(400, "instructions or text required")
    wf = mgr.create(
        texts,
        origin=req.origin,
        context=req.context,
        sequential=req.sequential,
        idempotency_prefix=req.idempotency_prefix,
        wrap=req.wrap,
    )
    mgr.dispatch_outbox()
    return {"ok": True, "workflow": wf}


@app.get("/v1/workflows/{wid}")
def get_wf(wid: str) -> dict[str, Any]:
    wf = mgr.get_workflow(wid)
    if not wf:
        raise HTTPException(404, "not found")
    return {"ok": True, "workflow": wf}


@app.post("/v1/workflows/{wid}/wait")
def wait_wf(wid: str, req: WaitReq) -> dict[str, Any]:
    deadline = time.time() + max(0.0, min(req.timeout_s, 300.0))
    while True:
        wf = mgr.get_workflow(wid)
        if not wf:
            raise HTTPException(404, "not found")
        status = str(wf.get("status") or "")
        if status in {"COMPLETED", "PARTIAL_FAILURE", "FAILED"}:
            return {"ok": True, "workflow": wf}
        if time.time() >= deadline:
            return {"ok": False, "workflow": wf, "timeout": True}
        time.sleep(0.5)


@app.post("/v1/worker/claim")
def claim(worker_id: str = "", execute: str = "hermes") -> dict[str, Any]:
    mgr.recover_stale()
    mgr.dispatch_outbox()
    job = mgr.claim(worker_id or WORKER_ID, execute=execute or "hermes")
    return {"ok": True, "job": job}


@app.post("/v1/jobs/{jid}/heartbeat")
def heartbeat(jid: str, worker_id: str = "") -> dict[str, Any]:
    ok = mgr.heartbeat(jid, worker_id or WORKER_ID)
    return {"ok": ok}


@app.post("/v1/jobs/{jid}/complete")
def complete(jid: str, req: CompleteReq) -> dict[str, Any]:
    try:
        wf = mgr.complete(jid, req.result)
    except KeyError:
        raise HTTPException(404, "not found") from None
    mgr.dispatch_outbox()
    return {"ok": True, "workflow": wf}


@app.post("/v1/jobs/{jid}/fail")
def fail(jid: str, req: FailReq) -> dict[str, Any]:
    try:
        wf = mgr.fail(jid, req.error)
    except KeyError:
        raise HTTPException(404, "not found") from None
    mgr.dispatch_outbox()
    return {"ok": True, "workflow": wf}


@app.post("/v1/schedules")
def upsert_schedule(req: ScheduleReq) -> dict[str, Any]:
    expr = (req.cron_expr or "").strip() or (extract_cron_expr(req.time) or "")
    if not expr:
        expr = extract_cron_expr(req.text) or ""
    if not expr:
        raise HTTPException(400, "cron_expr or time required")
    if not req.text.strip():
        raise HTTPException(400, "text required")
    row = mgr.upsert_schedule(
        cron_expr=expr,
        text=req.text,
        name=req.name,
        tz_name=req.timezone,
        origin=req.origin,
        context=req.context,
        schedule_id=req.id,
        enabled=req.enabled,
        next_run_at=_parse_next_run(req.next_run_at),
        cadence=req.cadence or extract_cadence(req.text),
    )
    return {"ok": True, "schedule": row}


@app.get("/v1/schedules")
def list_schedules() -> dict[str, Any]:
    rows = mgr.store.list_schedules()
    return {"ok": True, "schedules": rows}


@app.delete("/v1/schedules/{sid}")
def delete_schedule(sid: str) -> dict[str, Any]:
    mgr.store.delete_schedule(sid)
    return {"ok": True}


@app.post("/v1/schedules/tick")
def tick() -> dict[str, Any]:
    ids = mgr.fire_due_schedules(datetime.now(timezone.utc))
    mgr.dispatch_outbox()
    return {"ok": True, "workflows": ids}


@app.post("/v1/debug/stale")
def stale() -> dict[str, Any]:
    n = mgr.recover_stale()
    mgr.dispatch_outbox()
    return {"ok": True, "requeued": n}
