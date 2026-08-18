"""Postgres canonical store for workflow (schema wf)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS wf;
CREATE TABLE IF NOT EXISTS wf.workflows (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  origin JSONB NOT NULL DEFAULT '{}'::jsonb,
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS wf.jobs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL REFERENCES wf.workflows(id),
  seq INT NOT NULL DEFAULT 1,
  parent_job_id TEXT,
  instruction TEXT NOT NULL,
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
  status TEXT NOT NULL,
  attempts INT NOT NULL DEFAULT 0,
  max_attempts INT NOT NULL DEFAULT 3,
  idempotency_key TEXT UNIQUE,
  scheduled_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  lease_until TIMESTAMPTZ,
  worker_id TEXT,
  result JSONB,
  error TEXT
);
CREATE TABLE IF NOT EXISTS wf.job_attempts (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  attempt_n INT NOT NULL,
  worker_id TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status TEXT,
  error TEXT,
  result JSONB
);
CREATE TABLE IF NOT EXISTS wf.outbox (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  payload JSONB NOT NULL,
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS wf.schedules (
  id TEXT PRIMARY KEY,
  name TEXT,
  cron_expr TEXT NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
  enabled BOOLEAN NOT NULL DEFAULT true,
  text TEXT NOT NULL,
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  origin JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_fired_at TIMESTAMPTZ,
  next_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _json(val: Any) -> str:
    return json.dumps(val if val is not None else {}, ensure_ascii=False)


def _row(d: Any) -> dict[str, Any]:
    if d is None:
        return {}
    return dict(d)


class PostgresStore:
    def __init__(self, dsn: str) -> None:
        import psycopg
        from psycopg.rows import dict_row

        self._psycopg = psycopg
        self._dsn = dsn
        self._dict_row = dict_row
        self._ensure()

    def _conn(self):
        return self._psycopg.connect(self._dsn, row_factory=self._dict_row)

    def _ensure(self) -> None:
        with self._conn() as c:
            for stmt in SCHEMA_SQL.split(";"):
                s = stmt.strip()
                if s:
                    c.execute(s)
            c.commit()

    def insert_bundle(
        self,
        wf: dict[str, Any],
        jobs: list[dict[str, Any]],
        outbox: list[dict[str, Any]],
    ) -> None:
        with self._conn() as c:
            try:
                c.execute(
                    """INSERT INTO wf.workflows (id,status,origin,context,created_at,updated_at,completed_at)
                       VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)""",
                    (
                        wf["id"],
                        wf["status"],
                        _json(wf.get("origin")),
                        _json(wf.get("context")),
                        wf.get("created_at"),
                        wf.get("updated_at"),
                        wf.get("completed_at"),
                    ),
                )
                for row in jobs:
                    c.execute(
                        """INSERT INTO wf.jobs (
                             id,workflow_id,seq,parent_job_id,instruction,context,dependencies,status,
                             attempts,max_attempts,idempotency_key,scheduled_at,started_at,completed_at,
                             lease_until,worker_id,result,error
                           ) VALUES (
                             %s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s
                           )""",
                        (
                            row["id"],
                            row["workflow_id"],
                            int(row.get("seq") or 1),
                            row.get("parent_job_id"),
                            row["instruction"],
                            _json(row.get("context")),
                            _json(row.get("dependencies") or []),
                            row["status"],
                            int(row.get("attempts") or 0),
                            int(row.get("max_attempts") or 3),
                            row.get("idempotency_key"),
                            row.get("scheduled_at"),
                            row.get("started_at"),
                            row.get("completed_at"),
                            row.get("lease_until"),
                            row.get("worker_id"),
                            _json(row.get("result")) if row.get("result") is not None else None,
                            row.get("error"),
                        ),
                    )
                for row in outbox:
                    c.execute(
                        "INSERT INTO wf.outbox (id,job_id,payload,published_at) VALUES (%s,%s,%s::jsonb,%s)",
                        (row["id"], row["job_id"], _json(row.get("payload")), row.get("published_at")),
                    )
                c.commit()
            except Exception as e:
                c.rollback()
                if "idempotency" in str(e).lower() or "unique" in str(e).lower():
                    raise KeyError("idempotency_key") from e
                raise

    def insert_workflow(self, row: dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO wf.workflows (id,status,origin,context,created_at,updated_at,completed_at)
                   VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)""",
                (
                    row["id"],
                    row["status"],
                    _json(row.get("origin")),
                    _json(row.get("context")),
                    row.get("created_at"),
                    row.get("updated_at"),
                    row.get("completed_at"),
                ),
            )
            c.commit()

    def get_workflow(self, wid: str) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM wf.workflows WHERE id=%s", (wid,))
            row = cur.fetchone()
            return _row(row) if row else None

    def update_workflow(self, wid: str, **fields: Any) -> None:
        fields["updated_at"] = datetime.now(timezone.utc)
        cols = []
        vals: list[Any] = []
        for k, v in fields.items():
            if k in {"origin", "context"}:
                cols.append(f"{k}=%s::jsonb")
                vals.append(_json(v))
            else:
                cols.append(f"{k}=%s")
                vals.append(v)
        vals.append(wid)
        with self._conn() as c:
            c.execute(f"UPDATE wf.workflows SET {', '.join(cols)} WHERE id=%s", vals)
            c.commit()

    def insert_job(self, row: dict[str, Any]) -> None:
        with self._conn() as c:
            try:
                c.execute(
                    """INSERT INTO wf.jobs (
                         id,workflow_id,seq,parent_job_id,instruction,context,dependencies,status,
                         attempts,max_attempts,idempotency_key,scheduled_at,started_at,completed_at,
                         lease_until,worker_id,result,error
                       ) VALUES (
                         %s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s
                       )""",
                    (
                        row["id"],
                        row["workflow_id"],
                        int(row.get("seq") or 1),
                        row.get("parent_job_id"),
                        row["instruction"],
                        _json(row.get("context")),
                        _json(row.get("dependencies") or []),
                        row["status"],
                        int(row.get("attempts") or 0),
                        int(row.get("max_attempts") or 3),
                        row.get("idempotency_key"),
                        row.get("scheduled_at"),
                        row.get("started_at"),
                        row.get("completed_at"),
                        row.get("lease_until"),
                        row.get("worker_id"),
                        _json(row.get("result")) if row.get("result") is not None else None,
                        row.get("error"),
                    ),
                )
                c.commit()
            except Exception as e:
                if "idempotency" in str(e).lower() or "unique" in str(e).lower():
                    raise KeyError("idempotency_key") from e
                raise

    def job_by_idempotency(self, key: str) -> Optional[dict[str, Any]]:
        if not key:
            return None
        with self._conn() as c:
            cur = c.execute("SELECT * FROM wf.jobs WHERE idempotency_key=%s", (key,))
            row = cur.fetchone()
            return _row(row) if row else None

    def get_job(self, jid: str) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM wf.jobs WHERE id=%s", (jid,))
            row = cur.fetchone()
            if not row:
                return None
            d = _row(row)
            deps = d.get("dependencies")
            if isinstance(deps, str):
                d["dependencies"] = json.loads(deps)
            return d

    def jobs_for_workflow(self, wid: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM wf.jobs WHERE workflow_id=%s ORDER BY seq ASC", (wid,))
            rows = []
            for row in cur.fetchall() or []:
                d = _row(row)
                deps = d.get("dependencies")
                if isinstance(deps, str):
                    d["dependencies"] = json.loads(deps)
                rows.append(d)
            return rows

    def running_jobs(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM wf.jobs WHERE status='RUNNING'")
            rows = []
            for row in cur.fetchall() or []:
                d = _row(row)
                deps = d.get("dependencies")
                if isinstance(deps, str):
                    d["dependencies"] = json.loads(deps)
                rows.append(d)
            return rows

    def update_job(self, jid: str, **fields: Any) -> None:
        cols = []
        vals: list[Any] = []
        for k, v in fields.items():
            if k in {"context", "dependencies", "result"}:
                cols.append(f"{k}=%s::jsonb")
                vals.append(_json(v) if v is not None else None)
            else:
                cols.append(f"{k}=%s")
                vals.append(v)
        vals.append(jid)
        with self._conn() as c:
            c.execute(f"UPDATE wf.jobs SET {', '.join(cols)} WHERE id=%s", vals)
            c.commit()

    def insert_attempt(self, row: dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO wf.job_attempts (id,job_id,attempt_n,worker_id,started_at,finished_at,status,error,result)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    row["id"],
                    row["job_id"],
                    row.get("attempt_n"),
                    row.get("worker_id"),
                    row.get("started_at"),
                    row.get("finished_at"),
                    row.get("status"),
                    row.get("error"),
                    _json(row.get("result")) if row.get("result") is not None else None,
                ),
            )
            c.commit()

    def insert_outbox(self, row: dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO wf.outbox (id,job_id,payload,published_at) VALUES (%s,%s,%s::jsonb,%s)",
                (row["id"], row["job_id"], _json(row.get("payload")), row.get("published_at")),
            )
            c.commit()

    def unpublished_outbox(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM wf.outbox WHERE published_at IS NULL ORDER BY created_at ASC")
            return [_row(r) for r in (cur.fetchall() or [])]

    def mark_outbox_published(self, oid: str, when: datetime) -> None:
        with self._conn() as c:
            c.execute("UPDATE wf.outbox SET published_at=%s WHERE id=%s", (when, oid))
            c.commit()

    def enqueue(self, job_id: str) -> None:
        import os
        try:
            import valkey  # type: ignore
        except ImportError:  # pragma: no cover - local fallback until valkey is installed
            import redis as valkey  # type: ignore

        url = (
            os.environ.get("VALKEY_URL")
            or os.environ.get("REDIS_URL")
            or "valkey://redis:6379/0"
        )
        client_cls = getattr(valkey, "Valkey", None) or getattr(valkey, "Redis")
        r = client_cls.from_url(url)
        r.rpush("wf:queue", job_id)

    def dequeue(self) -> Optional[str]:
        import os
        try:
            import valkey  # type: ignore
        except ImportError:  # pragma: no cover - local fallback until valkey is installed
            import redis as valkey  # type: ignore

        url = (
            os.environ.get("VALKEY_URL")
            or os.environ.get("REDIS_URL")
            or "valkey://redis:6379/0"
        )
        client_cls = getattr(valkey, "Valkey", None) or getattr(valkey, "Redis")
        r = client_cls.from_url(url)
        raw = r.lpop("wf:queue")
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8", "replace")
        return str(raw)

    def insert_schedule(self, row: dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO wf.schedules (id,name,cron_expr,timezone,enabled,text,context,origin,last_fired_at,next_run_at,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)""",
                (
                    row["id"],
                    row.get("name"),
                    row["cron_expr"],
                    row.get("timezone") or "Asia/Ho_Chi_Minh",
                    bool(row.get("enabled", True)),
                    row["text"],
                    _json(row.get("context")),
                    _json(row.get("origin")),
                    row.get("last_fired_at"),
                    row.get("next_run_at"),
                    row.get("created_at") or datetime.now(timezone.utc),
                ),
            )
            c.commit()

    def get_schedule(self, sid: str) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM wf.schedules WHERE id=%s", (sid,))
            row = cur.fetchone()
            return _row(row) if row else None

    def list_schedules(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM wf.schedules ORDER BY created_at ASC")
            return [_row(r) for r in (cur.fetchall() or [])]

    def update_schedule(self, sid: str, **fields: Any) -> None:
        cols = []
        vals: list[Any] = []
        for k, v in fields.items():
            if k in {"context", "origin"}:
                cols.append(f"{k}=%s::jsonb")
                vals.append(_json(v))
            else:
                cols.append(f"{k}=%s")
                vals.append(v)
        vals.append(sid)
        with self._conn() as c:
            c.execute(f"UPDATE wf.schedules SET {', '.join(cols)} WHERE id=%s", vals)
            c.commit()

    def delete_schedule(self, sid: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM wf.schedules WHERE id=%s", (sid,))
            c.commit()

    def due_schedules(self, now: datetime) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM wf.schedules WHERE enabled=true AND next_run_at IS NOT NULL AND next_run_at<=%s",
                (now,),
            )
            return [_row(r) for r in (cur.fetchall() or [])]
