"""Hermes Authorization — Workspace ACL (default DENY) before Agent/LLM.

Day-1 LocalAuthorizationProvider backed by PostgreSQL.
Seeds workspaces from ZALO_ALLOWED_THREADS when present.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import psycopg
from fastapi import FastAPI, HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://hermes:hermes@postgres:5432/hermes_memory",
)
SEED_THREADS = [
    t.strip()
    for t in os.environ.get("ZALO_ALLOWED_THREADS", "").split(",")
    if t.strip()
]
SEED_HOME = os.environ.get("ZALO_HOME_CHANNEL", "").strip()

app = FastAPI(title="assistant-authz", version="1.0.0")
pool: ConnectionPool | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS authz_identities (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS authz_external_identities (
  id TEXT PRIMARY KEY,
  identity_id TEXT NOT NULL REFERENCES authz_identities(id),
  platform TEXT NOT NULL,
  external_id TEXT NOT NULL,
  current_alias TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (platform, external_id)
);
CREATE TABLE IF NOT EXISTS authz_workspaces (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS authz_external_workspaces (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES authz_workspaces(id),
  platform TEXT NOT NULL,
  external_type TEXT NOT NULL DEFAULT 'group',
  external_id TEXT NOT NULL,
  current_alias TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (platform, external_id)
);
CREATE TABLE IF NOT EXISTS authz_roles (
  id TEXT PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS authz_permissions (
  id TEXT PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS authz_role_permissions (
  role_id TEXT NOT NULL REFERENCES authz_roles(id),
  permission_id TEXT NOT NULL REFERENCES authz_permissions(id),
  PRIMARY KEY (role_id, permission_id)
);
CREATE TABLE IF NOT EXISTS authz_workspace_acl (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES authz_workspaces(id),
  principal_type TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  effect TEXT NOT NULL CHECK (effect IN ('ALLOW','DENY')),
  role_id TEXT REFERENCES authz_roles(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (workspace_id, principal_type, principal_id)
);
CREATE TABLE IF NOT EXISTS authz_memberships (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES authz_workspaces(id),
  identity_id TEXT NOT NULL REFERENCES authz_identities(id),
  role_id TEXT NOT NULL REFERENCES authz_roles(id),
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (workspace_id, identity_id)
);
CREATE TABLE IF NOT EXISTS authz_audit (
  id TEXT PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  actor_identity_id TEXT,
  workspace_id TEXT,
  action TEXT NOT NULL,
  decision TEXT NOT NULL,
  source TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'
);
"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}" if prefix else uuid.uuid4().hex


def _conn():
    assert pool is not None
    return pool.connection()


def _seed(conn) -> None:
    # roles + permissions
    roles = [("role-admin", "ADMIN"), ("role-leader", "LEADER"), ("role-user", "USER")]
    for rid, code in roles:
        conn.execute(
            "INSERT INTO authz_roles (id, code) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
            (rid, code),
        )
    perms = [
        "KNOWLEDGE_READ",
        "KNOWLEDGE_SEARCH",
        "TOOL_EXECUTE",
        "API_READ",
        "USER_READ",
        "USER_APPROVE",
        "SECRET_READ",
    ]
    for code in perms:
        conn.execute(
            "INSERT INTO authz_permissions (id, code) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
            (_id("perm-"), code),
        )
    # ADMIN gets all; USER gets read/search/tool
    conn.execute(
        """
        INSERT INTO authz_role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM authz_roles r CROSS JOIN authz_permissions p
        WHERE r.code = 'ADMIN'
        ON CONFLICT DO NOTHING
        """
    )
    conn.execute(
        """
        INSERT INTO authz_role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM authz_roles r
        JOIN authz_permissions p ON p.code IN ('KNOWLEDGE_READ','KNOWLEDGE_SEARCH','TOOL_EXECUTE','API_READ','USER_READ')
        WHERE r.code IN ('LEADER','USER')
        ON CONFLICT DO NOTHING
        """
    )
    conn.execute(
        """
        INSERT INTO authz_role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM authz_roles r
        JOIN authz_permissions p ON p.code = 'SECRET_READ'
        WHERE r.code IN ('ADMIN','LEADER')
        ON CONFLICT DO NOTHING
        """
    )
    # seed Zalo workspaces from allowlist (default DENY — only ACL entries grant)
    for i, tid in enumerate(SEED_THREADS):
        alias = "home" if tid == SEED_HOME else f"zalo-group-{i+1}"
        # stable workspace id from external id
        ws_id = f"ws-zalo-{tid[-12:]}"
        conn.execute(
            "INSERT INTO authz_workspaces (id, status) VALUES (%s, 'ACTIVE') ON CONFLICT DO NOTHING",
            (ws_id,),
        )
        conn.execute(
            """
            INSERT INTO authz_external_workspaces
              (id, workspace_id, platform, external_type, external_id, current_alias)
            VALUES (%s, %s, 'ZALO', 'group', %s, %s)
            ON CONFLICT (platform, external_id) DO UPDATE
              SET current_alias = EXCLUDED.current_alias, updated_at = NOW()
            """,
            (_id("ews-"), ws_id, tid, alias),
        )
        # wildcard allow for any resolved identity with role-user (bootstrap)
        # principal_id='*' means any authenticated identity in this lab bootstrap
        conn.execute(
            """
            INSERT INTO authz_workspace_acl
              (id, workspace_id, principal_type, principal_id, effect, role_id)
            VALUES (%s, %s, 'USER', '*', 'ALLOW', 'role-user')
            ON CONFLICT (workspace_id, principal_type, principal_id) DO NOTHING
            """,
            (_id("acl-"), ws_id),
        )


@app.on_event("startup")
def startup() -> None:
    global pool
    pool = ConnectionPool(
        DSN,
        min_size=1,
        max_size=8,
        check=ConnectionPool.check_connection,
        kwargs={"row_factory": dict_row},
    )
    with _conn() as conn:
        conn.execute(SCHEMA)
        _seed(conn)
        conn.commit()


@app.get("/health")
def health() -> dict[str, Any]:
    ok = False
    try:
        with _conn() as conn:
            conn.execute("SELECT 1")
            ok = True
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": ok, "seed_threads": len(SEED_THREADS)}


class ResolveReq(BaseModel):
    platform: str = "ZALO"
    external_user_id: str
    external_alias: Optional[str] = None
    external_workspace_id: Optional[str] = None
    external_workspace_type: str = "group"


class AuthorizeReq(BaseModel):
    platform: str = "ZALO"
    external_user_id: str
    external_workspace_id: str
    permission: str = "KNOWLEDGE_READ"
    external_alias: Optional[str] = None


@app.post("/v1/resolve")
def resolve(req: ResolveReq) -> dict[str, Any]:
    """Resolve or create Hermes Identity + lookup Workspace."""
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT identity_id FROM authz_external_identities
            WHERE platform = %s AND external_id = %s
            """,
            (req.platform.upper(), req.external_user_id),
        ).fetchone()
        if row:
            identity_id = row["identity_id"]
            conn.execute(
                """
                UPDATE authz_external_identities
                SET current_alias = COALESCE(%s, current_alias), updated_at = NOW()
                WHERE platform = %s AND external_id = %s
                """,
                (req.external_alias, req.platform.upper(), req.external_user_id),
            )
        else:
            identity_id = _id("usr-")
            conn.execute(
                "INSERT INTO authz_identities (id, status) VALUES (%s, 'ACTIVE')",
                (identity_id,),
            )
            conn.execute(
                """
                INSERT INTO authz_external_identities
                  (id, identity_id, platform, external_id, current_alias)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    _id("ext-"),
                    identity_id,
                    req.platform.upper(),
                    req.external_user_id,
                    req.external_alias,
                ),
            )
        workspace = None
        if req.external_workspace_id:
            workspace = conn.execute(
                """
                SELECT w.id, w.status, e.current_alias, e.external_id
                FROM authz_external_workspaces e
                JOIN authz_workspaces w ON w.id = e.workspace_id
                WHERE e.platform = %s AND e.external_id = %s
                """,
                (req.platform.upper(), req.external_workspace_id),
            ).fetchone()
        conn.commit()
        return {
            "identity_id": identity_id,
            "workspace": workspace,
        }


@app.post("/v1/authorize")
def authorize(req: AuthorizeReq) -> dict[str, Any]:
    """Full pipeline: resolve → workspace ACL (default DENY) → membership/role → permission."""
    decision = "DENY"
    reason = "default_deny"
    role_code = None
    identity_id = None
    workspace_id = None

    with _conn() as conn:
        resolved = resolve(
            ResolveReq(
                platform=req.platform,
                external_user_id=req.external_user_id,
                external_alias=req.external_alias,
                external_workspace_id=req.external_workspace_id,
            )
        )
        identity_id = resolved["identity_id"]
        ws = resolved.get("workspace")
        if not ws:
            reason = "workspace_not_found"
        elif ws["status"] != "ACTIVE":
            reason = f"workspace_{ws['status'].lower()}"
            workspace_id = ws["id"]
        else:
            workspace_id = ws["id"]
            # Workspace ACL — principal-specific first; DENY beats ALLOW; else default DENY
            acl = conn.execute(
                """
                SELECT effect, role_id, principal_id FROM authz_workspace_acl
                WHERE workspace_id = %s AND principal_type = 'USER'
                  AND principal_id IN (%s, '*')
                ORDER BY CASE WHEN principal_id = %s THEN 0 ELSE 1 END
                """,
                (workspace_id, identity_id, identity_id),
            ).fetchall()
            allow = None
            role_id = "role-user"
            for a in acl:
                if a["effect"] == "DENY":
                    allow = False
                    reason = "acl_deny"
                    break
                if a["effect"] == "ALLOW" and allow is not False:
                    allow = True
                    role_id = a["role_id"] or "role-user"
            if allow is True:
                role_row = conn.execute(
                    "SELECT code FROM authz_roles WHERE id = %s", (role_id,)
                ).fetchone()
                role_code = role_row["code"] if role_row else "USER"
                ok = conn.execute(
                    """
                    SELECT 1 FROM authz_role_permissions rp
                    JOIN authz_roles r ON r.id = rp.role_id
                    JOIN authz_permissions p ON p.id = rp.permission_id
                    WHERE r.code = %s AND p.code = %s
                    """,
                    (role_code, req.permission),
                ).fetchone()
                if ok:
                    decision = "ALLOW"
                    reason = "acl_allow"
                    conn.execute(
                        """
                        INSERT INTO authz_memberships (id, workspace_id, identity_id, role_id, status)
                        VALUES (%s, %s, %s, %s, 'ACTIVE')
                        ON CONFLICT (workspace_id, identity_id) DO UPDATE
                          SET status = 'ACTIVE', role_id = EXCLUDED.role_id, updated_at = NOW()
                        """,
                        (_id("mem-"), workspace_id, identity_id, role_id),
                    )
                else:
                    decision = "DENY"
                    reason = "permission_denied"
            elif allow is False:
                decision = "DENY"
            else:
                decision = "DENY"
                reason = "default_deny"

        conn.execute(
            """
            INSERT INTO authz_audit (id, actor_identity_id, workspace_id, action, decision, source, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                _id("aud-"),
                identity_id,
                workspace_id,
                f"authorize:{req.permission}",
                decision,
                req.platform,
                Json(
                    {
                        "external_user_id": req.external_user_id,
                        "external_workspace_id": req.external_workspace_id,
                        "reason": reason,
                        "role": role_code,
                    }
                ),
            ),
        )
        conn.commit()

    return {
        "decision": decision,
        "reason": reason,
        "identity_id": identity_id,
        "workspace_id": workspace_id,
        "role": role_code,
        "permission": req.permission,
        "allowed": decision == "ALLOW",
    }


@app.get("/v1/workspaces")
def list_workspaces() -> dict[str, Any]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT w.id, w.status, e.platform, e.external_id, e.current_alias
            FROM authz_workspaces w
            LEFT JOIN authz_external_workspaces e ON e.workspace_id = w.id
            ORDER BY w.created_at
            """
        ).fetchall()
    return {"workspaces": rows}
