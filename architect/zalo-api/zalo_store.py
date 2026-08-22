# -*- coding: utf-8 -*-
"""PostgreSQL store for Zalo admin / users / DMs / groups (replaces text allowlists).

SoT when DATABASE_URL is set and reachable. File paths remain as migrate/fallback.
Kinds: admin (sole), user, dm, group (allowed), denied (kicked group/thread).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

log = logging.getLogger("zalo-api.store")

DSN = (os.environ.get("DATABASE_URL") or "").strip()
_pool = None
_ready = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS zalo_entities (
  kind TEXT NOT NULL,
  id TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (kind, id)
);
CREATE INDEX IF NOT EXISTS zalo_entities_kind_status_idx
  ON zalo_entities (kind, status);
CREATE TABLE IF NOT EXISTS zalo_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

KINDS = frozenset({"admin", "user", "dm", "group", "denied"})


def available() -> bool:
    return bool(DSN) and _ensure()


def _ensure() -> bool:
    global _pool, _ready
    if not DSN:
        return False
    if _ready and _pool is not None:
        return True
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        if _pool is None:
            _pool = ConnectionPool(
                conninfo=DSN,
                min_size=1,
                max_size=4,
                kwargs={"row_factory": dict_row},
                open=True,
            )
        with _pool.connection() as conn:
            conn.execute(SCHEMA)
            conn.commit()
        _ready = True
        return True
    except Exception as e:
        log.warning("zalo postgres unavailable: %s", type(e).__name__)
        _ready = False
        return False


def list_entities(kind: str, *, status: Optional[str] = "active") -> list[dict[str, str]]:
    if not _ensure():
        return []
    kind = kind.strip().lower()
    with _pool.connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT id, name, status FROM zalo_entities WHERE kind=%s AND status=%s ORDER BY id",
                (kind, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, status FROM zalo_entities WHERE kind=%s ORDER BY id",
                (kind,),
            ).fetchall()
    return [{"id": str(r["id"]), "name": str(r.get("name") or ""), "status": str(r.get("status") or "")} for r in rows]


def get_admin() -> Optional[dict[str, str]]:
    rows = list_entities("admin", status="active")
    return rows[0] if rows else None


def set_admin(uid: str, name: str = "") -> dict[str, str]:
    uid = (uid or "").strip()
    if not uid:
        raise ValueError("admin uid required")
    if not _ensure():
        raise RuntimeError("postgres unavailable")
    name = (name or "").strip()
    with _pool.connection() as conn:
        conn.execute("DELETE FROM zalo_entities WHERE kind='admin'")
        conn.execute(
            """
            INSERT INTO zalo_entities (kind, id, name, status, updated_at)
            VALUES ('admin', %s, %s, 'active', NOW())
            """,
            (uid, name),
        )
        conn.commit()
    return {"id": uid, "name": name, "status": "active"}


def upsert_entity(
    kind: str,
    eid: str,
    *,
    name: str = "",
    status: str = "active",
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    kind = (kind or "").strip().lower()
    eid = (eid or "").strip()
    if kind not in KINDS:
        raise ValueError(f"invalid kind: {kind}")
    if not eid:
        raise ValueError("id required")
    if not _ensure():
        raise RuntimeError("postgres unavailable")
    name = (name or "").strip()
    status = (status or "active").strip() or "active"
    meta_obj = meta if isinstance(meta, dict) else {}
    with _pool.connection() as conn:
        from psycopg.types.json import Json

        conn.execute(
            """
            INSERT INTO zalo_entities (kind, id, name, status, meta, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (kind, id) DO UPDATE SET
              name = CASE WHEN EXCLUDED.name <> '' THEN EXCLUDED.name ELSE zalo_entities.name END,
              status = EXCLUDED.status,
              meta = zalo_entities.meta || EXCLUDED.meta,
              updated_at = NOW()
            """,
            (kind, eid, name, status, Json(meta_obj)),
        )
        conn.commit()
    return {"id": eid, "name": name, "status": status, "kind": kind}


def delete_entity(kind: str, eid: str) -> bool:
    if not _ensure():
        return False
    with _pool.connection() as conn:
        cur = conn.execute(
            "DELETE FROM zalo_entities WHERE kind=%s AND id=%s",
            (kind.strip().lower(), eid.strip()),
        )
        conn.commit()
        return (cur.rowcount or 0) > 0


def set_status(kind: str, eid: str, status: str) -> bool:
    if not _ensure():
        return False
    with _pool.connection() as conn:
        cur = conn.execute(
            """
            UPDATE zalo_entities SET status=%s, updated_at=NOW()
            WHERE kind=%s AND id=%s
            """,
            (status.strip(), kind.strip().lower(), eid.strip()),
        )
        conn.commit()
        return (cur.rowcount or 0) > 0


def migrate_from_files(
    *,
    admin_file: str,
    allowed_threads_file: str,
    denied_threads_file: str,
    allowed_users_file: str,
) -> dict[str, int]:
    """One-shot import from legacy text files when postgres is empty."""
    counts = {"admin": 0, "group": 0, "denied": 0, "user": 0, "dm": 0}
    if not _ensure():
        return counts
    with _pool.connection() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM zalo_entities").fetchone()
        if int((n or {}).get("c") or 0) > 0:
            return counts

    def _parse_lines(path: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        try:
            if not os.path.isfile(path):
                return out
            with open(path, encoding="utf-8") as f:
                for line in f:
                    raw = line.strip()
                    if not raw or raw.startswith("#"):
                        continue
                    if "|" in raw:
                        a, b = raw.split("|", 1)
                    elif " #" in raw:
                        a, b = raw.split(" #", 1)
                    else:
                        a, b = raw, ""
                    a = a.strip()
                    if a:
                        out.append((a, b.strip()))
        except OSError:
            pass
        return out

    admins = _parse_lines(admin_file)
    if admins:
        set_admin(admins[0][0], admins[0][1])
        counts["admin"] = 1
    for tid, name in _parse_lines(allowed_threads_file):
        upsert_entity("group", tid, name=name, status="active")
        counts["group"] += 1
    for tid, _ in _parse_lines(denied_threads_file):
        upsert_entity("denied", tid, status="denied")
        counts["denied"] += 1
    for uid, name in _parse_lines(allowed_users_file):
        upsert_entity("user", uid, name=name, status="active")
        upsert_entity("dm", uid, name=name, status="active")
        counts["user"] += 1
        counts["dm"] += 1
    return counts


def export_snapshot() -> dict[str, Any]:
    if not _ensure():
        return {"ok": False, "backend": "none"}
    return {
        "ok": True,
        "backend": "postgres",
        "admin": get_admin(),
        "users": list_entities("user"),
        "dms": list_entities("dm"),
        "groups": list_entities("group"),
        "denied": list_entities("denied", status=None),
    }
