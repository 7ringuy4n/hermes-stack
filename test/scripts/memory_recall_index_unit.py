#!/usr/bin/env python3
"""Static contract for indexed knowledge and historical-session recall."""
from __future__ import annotations

import ast
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    path = root / "architect" / "memory" / "memory-manager" / "app.py"
    source = path.read_text(encoding="utf-8")
    ast.parse(source)
    assert "memories_session_idx" in source
    assert "memories_thread_session_created_idx" in source
    recall = source.split("def recall(req: RecallReq)", 1)[1]
    recall = recall.split('@app.get("/v1/search")', 1)[0]
    assert 'clauses.append("session_id = %s")' in recall
    assert 'clauses.append("created_at >= %s")' in recall
    assert 'clauses.append("created_at <= %s")' in recall
    assert "base_clauses = list(clauses)" in recall
    assert "to_tsvector('simple', coalesce(content, ''))" in recall
    assert "AND content ILIKE %s" in recall
    primary = recall.split("fallback_sql", 1)[0]
    assert " OR content ILIKE " not in primary
    assert '"session_id": r["session_id"]' in recall
    lab = (root / "test" / "scripts" / "memory_scale_10m_lab.py").read_text(
        encoding="utf-8"
    )
    assert "ROWS = 10_000_000" in lab
    assert "knowledge_accuracy" in lab and "old_session_accuracy" in lab
    assert "DROP TABLE IF EXISTS" in lab
    print("memory_recall_index_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
