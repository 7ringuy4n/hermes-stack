"""In-memory canonical store (unit tests). Postgres store is postgres.py."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStore:
    def __init__(self) -> None:
        self.workflows: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.attempts: list[dict[str, Any]] = []
        self.outbox: list[dict[str, Any]] = []
        self.schedules: dict[str, dict[str, Any]] = {}
        self.queue: list[str] = []

    def insert_bundle(
        self,
        wf: dict[str, Any],
        jobs: list[dict[str, Any]],
        outbox: list[dict[str, Any]],
    ) -> None:
        self.insert_workflow(wf)
        for job in jobs:
            self.insert_job(job)
        for row in outbox:
            self.insert_outbox(row)

    def insert_workflow(self, row: dict[str, Any]) -> None:
        self.workflows[row["id"]] = row

    def get_workflow(self, wid: str) -> Optional[dict[str, Any]]:
        row = self.workflows.get(wid)
        return copy.deepcopy(row) if row else None

    def update_workflow(self, wid: str, **fields: Any) -> None:
        row = self.workflows[wid]
        row.update(fields)
        row["updated_at"] = utcnow()

    def insert_job(self, row: dict[str, Any]) -> None:
        if row.get("idempotency_key"):
            for existing in self.jobs.values():
                if existing.get("idempotency_key") == row["idempotency_key"]:
                    raise KeyError("idempotency_key")
        self.jobs[row["id"]] = row

    def job_by_idempotency(self, key: str) -> Optional[dict[str, Any]]:
        if not key:
            return None
        for row in self.jobs.values():
            if row.get("idempotency_key") == key:
                return copy.deepcopy(row)
        return None

    def get_job(self, jid: str) -> Optional[dict[str, Any]]:
        row = self.jobs.get(jid)
        return copy.deepcopy(row) if row else None

    def jobs_for_workflow(self, wid: str) -> list[dict[str, Any]]:
        rows = [copy.deepcopy(j) for j in self.jobs.values() if j["workflow_id"] == wid]
        rows.sort(key=lambda j: int(j.get("seq") or 0))
        return rows

    def running_jobs(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(j) for j in self.jobs.values() if j.get("status") == "RUNNING"]

    def update_job(self, jid: str, **fields: Any) -> None:
        self.jobs[jid].update(fields)

    def insert_attempt(self, row: dict[str, Any]) -> None:
        self.attempts.append(row)

    def insert_outbox(self, row: dict[str, Any]) -> None:
        self.outbox.append(row)

    def unpublished_outbox(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(r) for r in self.outbox if r.get("published_at") is None]

    def mark_outbox_published(self, oid: str, when: datetime) -> None:
        for r in self.outbox:
            if r["id"] == oid:
                r["published_at"] = when

    def enqueue(self, job_id: str) -> None:
        self.queue.append(job_id)

    def dequeue(self) -> Optional[str]:
        if not self.queue:
            return None
        return self.queue.pop(0)

    def insert_schedule(self, row: dict[str, Any]) -> None:
        self.schedules[row["id"]] = row

    def get_schedule(self, sid: str) -> Optional[dict[str, Any]]:
        row = self.schedules.get(sid)
        return copy.deepcopy(row) if row else None

    def list_schedules(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(s) for s in self.schedules.values()]

    def update_schedule(self, sid: str, **fields: Any) -> None:
        self.schedules[sid].update(fields)

    def delete_schedule(self, sid: str) -> None:
        self.schedules.pop(sid, None)

    def due_schedules(self, now: datetime) -> list[dict[str, Any]]:
        out = []
        for s in self.schedules.values():
            if not s.get("enabled", True):
                continue
            nxt = s.get("next_run_at")
            if nxt is not None and nxt <= now:
                out.append(copy.deepcopy(s))
        return out
