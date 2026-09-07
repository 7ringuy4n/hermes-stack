#!/usr/bin/env python3
"""VPS lab: exact knowledge and old-session recall over 10 million rows.

The corpus is generated in an isolated unlogged table, measured with the same
PostgreSQL predicates/index families as Memory Manager, and removed in finally.
No generated corpus is copied into the repository or retained on the VPS.
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-memory-scale-10m"


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = connect()
    remote = r'''
set -euo pipefail
python3 - <<'PY'
import json
import os
import subprocess

ROWS = 10_000_000
MAX_QUERY_MS = float(os.environ.get("MEMORY_SCALE_MAX_QUERY_MS", "2000"))
TABLE = "memory_scale_lab"

def psql(sql, *, tuples=False):
    args = [
        "docker", "exec", "-i", "postgres", "sh", "-lc",
        'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
        + ("-At" if tuples else ""),
    ]
    completed = subprocess.run(args, input=sql, text=True, capture_output=True, timeout=1800)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout)[-1000:])
    return completed.stdout.strip()

def explain(sql):
    raw = psql("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, tuples=True)
    plan = json.loads(raw)[0]
    return float(plan.get("Execution Time") or 0), json.dumps(plan.get("Plan") or {})

checks = []
def note(name, ok, detail):
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS" if ok else "FAIL"), name, str(detail)[:220])

try:
    reachable = psql("SELECT 1;", tuples=True)
    note("database_access", reachable == "1", "postgres reachable")
    psql(f"DROP TABLE IF EXISTS {TABLE};")
    psql(f"""
      CREATE UNLOGGED TABLE {TABLE} (
        id BIGINT PRIMARY KEY,
        type TEXT NOT NULL,
        content TEXT NOT NULL,
        importance REAL NOT NULL,
        session_id TEXT,
        thread_id TEXT,
        staged BOOLEAN NOT NULL DEFAULT FALSE,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL
      );
      INSERT INTO {TABLE} (id,type,content,importance,session_id,thread_id,created_at)
      SELECT n,
             CASE WHEN n % 5 = 0 THEN 'task' ELSE 'fact' END,
             CASE
               WHEN n = 824731 THEN 'harborquartz knowledge anchor exact result'
               WHEN n = 1700003 THEN 'oldsession task cobalt itinerary exact result'
               ELSE 'synthetic memory filler ' || n::text
             END,
             CASE WHEN n IN (824731,1700003) THEN 0.99 ELSE 0.2 END,
             CASE WHEN n = 1700003 THEN 'session-target-2001'
                  ELSE 'session-' || (n % 200000)::text END,
             CASE WHEN n = 1700003 THEN 'thread-target'
                  ELSE 'thread-' || (n % 10000)::text END,
             TIMESTAMPTZ '2010-01-01 00:00:00+00' + (n || ' seconds')::interval
      FROM generate_series(1, {ROWS}) AS n;
      CREATE INDEX {TABLE}_fts_idx ON {TABLE}
        USING GIN (to_tsvector('simple', coalesce(content, ''))) WHERE active;
      CREATE INDEX {TABLE}_session_idx ON {TABLE} (session_id) WHERE active;
      CREATE INDEX {TABLE}_thread_session_created_idx ON {TABLE}
        (thread_id, session_id, created_at DESC) WHERE active AND NOT staged;
      ANALYZE {TABLE};
    """)
    count = int(psql(f"SELECT COUNT(*) FROM {TABLE};", tuples=True))
    note("corpus_rows", count == ROWS, count)

    knowledge_sql = f"""
      SELECT id, content FROM {TABLE}
      WHERE active AND NOT staged
        AND to_tsvector('simple', coalesce(content, '')) @@ plainto_tsquery('simple', 'harborquartz knowledge anchor')
      ORDER BY importance DESC, created_at DESC LIMIT 8;
    """
    knowledge_ms, knowledge_plan = explain(knowledge_sql)
    knowledge = psql(knowledge_sql, tuples=True)
    note("knowledge_accuracy", knowledge.startswith("824731|harborquartz"), knowledge)
    note("knowledge_latency", 0 < knowledge_ms <= MAX_QUERY_MS, f"{knowledge_ms:.3f} ms")
    note("knowledge_index", "Index" in knowledge_plan or "Bitmap" in knowledge_plan, "indexed plan")

    session_sql = f"""
      SELECT id, content FROM {TABLE}
      WHERE active AND NOT staged AND thread_id='thread-target'
        AND session_id='session-target-2001'
        AND created_at >= TIMESTAMPTZ '2010-01-01 00:00:00+00'
        AND to_tsvector('simple', coalesce(content, '')) @@ plainto_tsquery('simple', 'oldsession task cobalt')
      ORDER BY importance DESC, created_at DESC LIMIT 8;
    """
    session_ms, session_plan = explain(session_sql)
    session = psql(session_sql, tuples=True)
    note("old_session_accuracy", session.startswith("1700003|oldsession"), session)
    note("old_session_latency", 0 < session_ms <= MAX_QUERY_MS, f"{session_ms:.3f} ms")
    note("old_session_index", "Index" in session_plan or "Bitmap" in session_plan, "indexed plan")

    ok = all(item["ok"] for item in checks)
    print("RESULT_JSON=" + json.dumps({
        "ok": ok,
        "rows": count,
        "knowledge_ms": knowledge_ms,
        "old_session_ms": session_ms,
        "checks": checks,
    }, separators=(",", ":")))
    print("VERDICT", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
finally:
    try:
        psql(f"DROP TABLE IF EXISTS {TABLE};")
    except Exception as exc:
        print("CLEANUP_FAIL", type(exc).__name__)
PY
'''
    try:
        raw = sudo_bash(client, remote, timeout=2400)
    finally:
        client.close()
    clean = "\n".join(
        line.strip()
        for line in raw.splitlines()
        if line.strip() and "password" not in line.lower()
    )
    (OUT / "remote.txt").write_text(clean, encoding="utf-8")
    payload = {}
    for line in clean.splitlines():
        if line.startswith("RESULT_JSON="):
            payload = json.loads(line.partition("=")[2])
    report = {
        "ts": ts(),
        "verdict": "PASS" if payload.get("ok") else "FAIL",
        "payload": payload,
    }
    (OUT / "SUMMARY.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(clean)
    print("REPORT", OUT / "SUMMARY.json", report["verdict"])
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
