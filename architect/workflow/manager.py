"""Workflow manager: Postgres/memory is source of truth; queue only delivers."""
from __future__ import annotations

import calendar
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from plan import (
    CADENCE_DAILY,
    CADENCE_MONTHLY,
    CADENCE_ONCE,
    CADENCE_WEEKLY,
    CADENCE_YEARLY,
    CADENCES,
    plan_graph_from_stored,
    plan_instructions,
    wrap_instruction,
)
from store import MemoryStore, utcnow

PENDING = "PENDING"
QUEUED = "QUEUED"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
RETRYING = "RETRYING"
DEAD = "DEAD"

WF_PENDING = "PENDING"
WF_RUNNING = "RUNNING"
WF_COMPLETED = "COMPLETED"
WF_PARTIAL = "PARTIAL_FAILURE"
WF_FAILED = "FAILED"

LEASE_S = 180
MAX_ATTEMPTS = 3


def _id(prefix: str) -> str:
    return prefix + secrets.token_hex(8)


def next_daily_cron(
    expr: str,
    tz_name: str,
    now: datetime,
    *,
    grace_s: int = 120,
) -> datetime:
    """Next daily fire in UTC.

    Same-minute create (e.g. 13:54:20 for 13:54 GMT+7) stays due *today* so the
    ticker can catch up, instead of jumping to tomorrow.
    """
    parts = (expr or "").split()
    if len(parts) < 2:
        raise ValueError("cron")
    minute = int(parts[0])
    hour = int(parts[1])
    tz = ZoneInfo(tz_name or "Asia/Ho_Chi_Minh")
    local = now.astimezone(tz)
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate > local:
        return candidate.astimezone(timezone.utc)
    delta = (local - candidate).total_seconds()
    if 0 <= delta <= max(0, int(grace_s)):
        return candidate.astimezone(timezone.utc)
    return (candidate + timedelta(days=1)).astimezone(timezone.utc)


def _clock_parts(expr: str) -> tuple[int, int]:
    parts = (expr or "").split()
    if len(parts) < 2:
        raise ValueError("cron")
    return int(parts[0]), int(parts[1])


def _add_months(dt: datetime, months: int) -> datetime:
    m0 = dt.month - 1 + months
    year = dt.year + m0 // 12
    month = m0 % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def resolve_cadence(raw: str, text: str = "") -> str:
    kind = (raw or "").strip().lower()
    if kind in CADENCES:
        return kind
    return CADENCE_ONCE


def next_run_after(
    cadence: str,
    expr: str,
    tz_name: str,
    now: datetime,
    *,
    grace_s: int = 0,
) -> datetime | None:
    """Next fire after `now`. once → None (caller deletes the row)."""
    kind = resolve_cadence(cadence)
    if kind == CADENCE_ONCE:
        return None
    if kind == CADENCE_DAILY:
        return next_daily_cron(expr, tz_name, now, grace_s=grace_s)
    minute, hour = _clock_parts(expr)
    tz = ZoneInfo(tz_name or "Asia/Ho_Chi_Minh")
    local = now.astimezone(tz)
    base = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if kind == CADENCE_WEEKLY:
        cand = base if base > local else base + timedelta(days=7)
        return cand.astimezone(timezone.utc)
    if kind == CADENCE_MONTHLY:
        cand = base if base > local else _add_months(base, 1)
        return cand.astimezone(timezone.utc)
    if kind == CADENCE_YEARLY:
        if base > local:
            cand = base
        else:
            try:
                cand = base.replace(year=base.year + 1)
            except ValueError:
                cand = base.replace(year=base.year + 1, day=28)
        return cand.astimezone(timezone.utc)
    return next_daily_cron(expr, tz_name, now, grace_s=grace_s)


class WorkflowManager:
    def __init__(self, store: MemoryStore, *, lease_s: int = LEASE_S) -> None:
        self.store = store
        self.lease_s = lease_s

    def create(
        self,
        instructions: list[str],
        *,
        origin: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        sequential: bool = False,
        idempotency_prefix: str | None = None,
        wrap: bool = True,
        task_details: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        texts = [str(x).strip() for x in instructions if str(x).strip()]
        if not texts:
            raise ValueError("no instructions")
        if idempotency_prefix:
            found = self.store.job_by_idempotency(f"{idempotency_prefix}:job_001")
            if found:
                return self.get_workflow(str(found["workflow_id"])) or {}
        now = utcnow()
        wid = _id("wf_")
        wf = {
            "id": wid,
            "status": WF_RUNNING,
            "origin": origin or {},
            "context": context or {},
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        job_ids: list[str] = []
        job_rows: list[dict[str, Any]] = []
        outbox_rows: list[dict[str, Any]] = []
        total = len(texts)
        details = [d for d in (task_details or []) if isinstance(d, dict)]
        for i, raw in enumerate(texts):
            jid = _id("job_")
            job_ids.append(jid)
            deps: list[str] = []
            if sequential and i > 0:
                deps = [job_ids[i - 1]]
            elif details and i < len(details):
                for idx in details[i].get("depends_on") or []:
                    try:
                        n = int(idx)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= n < i:
                        deps.append(job_ids[n])
            instruction = wrap_instruction(i + 1, total, raw) if wrap else raw
            key = None
            if idempotency_prefix:
                key = f"{idempotency_prefix}:job_{i+1:03d}"
            status = QUEUED if not deps else PENDING
            job_ctx = dict(context or {})
            if details and i < len(details):
                job_ctx["task"] = details[i]
            job_rows.append(
                {
                    "id": jid,
                    "workflow_id": wid,
                    "seq": i + 1,
                    "parent_job_id": deps[0] if deps else None,
                    "instruction": instruction,
                    "context": job_ctx,
                    "dependencies": deps,
                    "status": status,
                    "attempts": 0,
                    "max_attempts": MAX_ATTEMPTS,
                    "idempotency_key": key,
                    "scheduled_at": now,
                    "started_at": None,
                    "completed_at": None,
                    "lease_until": None,
                    "worker_id": None,
                    "result": None,
                    "error": None,
                }
            )
            if status == QUEUED:
                outbox_rows.append(
                    {"id": _id("ob_"), "job_id": jid, "payload": {"job_id": jid}, "published_at": None}
                )
        try:
            self.store.insert_bundle(wf, job_rows, outbox_rows)
        except KeyError:
            found = self.store.job_by_idempotency(f"{idempotency_prefix}:job_001" if idempotency_prefix else "")
            if found:
                return self.get_workflow(str(found["workflow_id"])) or wf
            raise
        return self.get_workflow(wid) or wf

    def create_from_text(self, text: str, **kwargs: Any) -> dict[str, Any]:
        return self.create(plan_instructions(text), **kwargs)

    def get_workflow(self, wid: str) -> Optional[dict[str, Any]]:
        wf = self.store.get_workflow(wid)
        if not wf:
            return None
        jobs = self.store.jobs_for_workflow(wid)
        jobs.sort(key=lambda j: int(j.get("seq") or 0) or str(j.get("id")))
        wf["jobs"] = jobs
        return wf

    def dispatch_outbox(self) -> int:
        n = 0
        now = utcnow()
        for row in self.store.unpublished_outbox():
            self.store.enqueue(str(row["job_id"]))
            self.store.mark_outbox_published(row["id"], now)
            n += 1
        return n

    def recover_stale(self, now: Optional[datetime] = None) -> int:
        now = now or utcnow()
        n = 0
        for job in self.store.running_jobs():
            lease = job.get("lease_until")
            if lease is not None and lease > now:
                continue
            n += 1
            self._requeue(job["id"], error="lease_expired")
        return n

    def claim(self, worker_id: str, execute: str | None = None) -> Optional[dict[str, Any]]:
        now = utcnow()
        want = str(execute or "hermes").lower()
        skipped: list[str] = []
        claimed: Optional[dict[str, Any]] = None
        while True:
            jid = self.store.dequeue()
            if not jid:
                break
            job = self.store.get_job(jid)
            if not job:
                continue
            if job["status"] not in {QUEUED, RETRYING, PENDING}:
                continue
            ctx_ex = str((job.get("context") or {}).get("execute") or "hermes").lower()
            if ctx_ex != want or not self._deps_ok(job):
                skipped.append(jid)
                continue
            attempts = int(job.get("attempts") or 0) + 1
            self.store.update_job(
                jid,
                status=RUNNING,
                attempts=attempts,
                started_at=now,
                worker_id=worker_id,
                lease_until=now + timedelta(seconds=self.lease_s),
            )
            self.store.insert_attempt(
                {
                    "id": _id("at_"),
                    "job_id": jid,
                    "attempt_n": attempts,
                    "worker_id": worker_id,
                    "started_at": now,
                    "finished_at": None,
                    "status": RUNNING,
                    "error": None,
                    "result": None,
                }
            )
            claimed = self.store.get_job(jid)
            break
        for jid in skipped:
            self.store.enqueue(jid)
        return claimed

    def heartbeat(self, job_id: str, worker_id: str) -> bool:
        job = self.store.get_job(job_id)
        if not job or job.get("worker_id") != worker_id or job.get("status") != RUNNING:
            return False
        self.store.update_job(job_id, lease_until=utcnow() + timedelta(seconds=self.lease_s))
        return True

    def complete(self, job_id: str, result: Any = None) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job["status"] == COMPLETED:
            return self.get_workflow(job["workflow_id"]) or {}
        now = utcnow()
        self.store.update_job(
            job_id,
            status=COMPLETED,
            result=result if isinstance(result, dict) else {"ok": True, "result": result},
            completed_at=now,
            lease_until=None,
            error=None,
        )
        self._unlock_children(job["workflow_id"], job_id)
        return self._refresh_workflow(job["workflow_id"])

    def fail(self, job_id: str, error: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        attempts = int(job.get("attempts") or 0)
        max_n = int(job.get("max_attempts") or MAX_ATTEMPTS)
        if attempts >= max_n:
            self.store.update_job(
                job_id,
                status=DEAD,
                error=str(error or "failed")[:800],
                completed_at=utcnow(),
                lease_until=None,
            )
        else:
            self._requeue(job_id, error=str(error or "failed")[:800])
        return self._refresh_workflow(job["workflow_id"])

    def upsert_schedule(
        self,
        *,
        cron_expr: str,
        text: str,
        name: str = "",
        tz_name: str = "Asia/Ho_Chi_Minh",
        origin: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        schedule_id: str | None = None,
        enabled: bool = True,
        next_run_at: datetime | None = None,
        cadence: str = "",
    ) -> dict[str, Any]:
        now = utcnow()
        sid = schedule_id or _id("sch_")
        existing = self.store.get_schedule(sid)
        row = existing or {
            "id": sid,
            "created_at": now,
        }
        kind = resolve_cadence(cadence or (existing or {}).get("cadence") or "", "")
        same_clock = bool(
            existing
            and str(existing.get("cron_expr") or "") == str(cron_expr)
            and str(existing.get("timezone") or "") == str(tz_name)
        )
        prev_next = existing.get("next_run_at") if existing else None
        if next_run_at is not None:
            nxt = next_run_at
        elif same_clock and prev_next is not None:
            nxt = prev_next
        else:
            nxt = next_daily_cron(cron_expr, tz_name, now)
        row.update(
            {
                "name": (name or text[:40] or sid).strip(),
                "cron_expr": cron_expr,
                "timezone": tz_name,
                "enabled": enabled,
                "text": text,
                "context": context or {},
                "origin": origin or {},
                "next_run_at": nxt,
                "cadence": kind,
            }
        )
        if existing:
            self.store.update_schedule(sid, **row)
        else:
            row["last_fired_at"] = None
            self.store.insert_schedule(row)
        return self.store.get_schedule(sid) or row

    def fire_due_schedules(self, now: Optional[datetime] = None) -> list[str]:
        if (os.getenv("SCHEDULE_URL") or "").strip():
            return []
        now = now or utcnow()
        created: list[str] = []
        seen: set[str] = set()
        for sch in self._schedules_to_fire(now):
            sid = str(sch.get("id") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            day = now.astimezone(ZoneInfo(str(sch.get("timezone") or "UTC"))).date().isoformat()
            kind = resolve_cadence(str(sch.get("cadence") or ""), "")
            if kind == CADENCE_ONCE:
                prefix = f"{sid}:once:{secrets.token_hex(8)}"
            else:
                prefix = f"{sid}:{day}"
            try:
                parts, details = plan_graph_from_stored(sch, str(sch.get("text") or ""))
                wf = self.create(
                    parts,
                    origin=sch.get("origin") or {},
                    context=sch.get("context") or {},
                    sequential=False,
                    task_details=details,
                    idempotency_prefix=prefix,
                )
            except (ValueError, KeyError):
                continue
            created.append(str(wf.get("id")))
            if kind == CADENCE_ONCE:
                self.store.delete_schedule(sid)
                continue
            try:
                nxt = next_run_after(
                    kind,
                    str(sch.get("cron_expr")),
                    str(sch.get("timezone")),
                    now + timedelta(seconds=1),
                    grace_s=0,
                )
            except ValueError:
                nxt = now + timedelta(days=1)
            if nxt is None:
                self.store.delete_schedule(sid)
                continue
            if nxt <= now:
                nxt = now + timedelta(days=1)
            self.store.update_schedule(
                sid, last_fired_at=now, next_run_at=nxt, cadence=kind
            )
        return created

    def _schedules_to_fire(self, now: datetime) -> list[dict[str, Any]]:
        rows = list(self.store.due_schedules(now))
        have = {str(s.get("id") or "") for s in rows}
        for sch in self.store.list_schedules():
            sid = str(sch.get("id") or "")
            if sid in have:
                continue
            if self._missed_today(sch, now):
                rows.append(sch)
        return rows

    def _missed_today(self, sch: dict[str, Any], now: datetime) -> bool:
        if not sch.get("enabled", True):
            return False
        parts = str(sch.get("cron_expr") or "").split()
        if len(parts) < 2:
            return False
        try:
            minute = int(parts[0])
            hour = int(parts[1])
        except ValueError:
            return False
        tz = ZoneInfo(str(sch.get("timezone") or "Asia/Ho_Chi_Minh"))
        local = now.astimezone(tz)
        candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > local:
            return False
        # Catch-up only within the same-minute grace window; otherwise a
        # schedule created long before its clock time would be fired
        # immediately (incorrect).
        grace_s = 120
        delta = (local - candidate).total_seconds()
        if delta < 0 or delta > grace_s:
            return False
        last = sch.get("last_fired_at")
        if last is not None:
            if getattr(last, "tzinfo", None) is None:
                last = last.replace(tzinfo=timezone.utc)
            if last.astimezone(tz).date() == local.date():
                return False
        return True

    def _deps_ok(self, job: dict[str, Any]) -> bool:
        for dep in job.get("dependencies") or []:
            other = self.store.get_job(str(dep))
            if not other or other.get("status") != COMPLETED:
                return False
        return True

    def _unlock_children(self, wid: str, completed_id: str) -> None:
        for job in self.store.jobs_for_workflow(wid):
            if job["status"] != PENDING:
                continue
            deps = [str(d) for d in (job.get("dependencies") or [])]
            if completed_id not in deps:
                continue
            if not self._deps_ok({**job, "dependencies": deps}):
                continue
            self.store.update_job(job["id"], status=QUEUED)
            self.store.insert_outbox(
                {
                    "id": _id("ob_"),
                    "job_id": job["id"],
                    "payload": {"job_id": job["id"]},
                    "published_at": None,
                }
            )

    def _requeue(self, job_id: str, error: str = "") -> None:
        self.store.update_job(
            job_id,
            status=QUEUED,
            error=error or None,
            worker_id=None,
            lease_until=None,
        )
        self.store.insert_outbox(
            {
                "id": _id("ob_"),
                "job_id": job_id,
                "payload": {"job_id": job_id},
                "published_at": None,
            }
        )

    def _refresh_workflow(self, wid: str) -> dict[str, Any]:
        jobs = self.store.jobs_for_workflow(wid)
        statuses = [j.get("status") for j in jobs]
        if statuses and all(s == COMPLETED for s in statuses):
            self.store.update_workflow(wid, status=WF_COMPLETED, completed_at=utcnow())
        elif statuses and all(s == DEAD for s in statuses):
            self.store.update_workflow(wid, status=WF_FAILED, completed_at=utcnow())
        elif DEAD in statuses and COMPLETED in statuses:
            self.store.update_workflow(wid, status=WF_PARTIAL, completed_at=utcnow())
        else:
            self.store.update_workflow(wid, status=WF_RUNNING, completed_at=None)
        return self.get_workflow(wid) or {"id": wid}
