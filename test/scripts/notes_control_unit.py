#!/usr/bin/env python3
"""Unit contract for multipurpose notes and active-request cancellation."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ZALO = ROOT / "hermes" / "main" / "plugins" / "zalo"
sys.path.insert(0, str(ZALO))

import classify_client  # noqa: E402
import notes_client  # noqa: E402


def _load_router_classify():
    sys.modules.setdefault("httpx", types.SimpleNamespace())
    path = ROOT / "architect" / "models" / "router-worker" / "classify.py"
    spec = importlib.util.spec_from_file_location("router_classify_notes_unit", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _note_plan() -> dict:
    return {
        "task_hint": "note",
        "task_type": "note",
        "execution_class": "interactive",
        "response_mode": "confirm",
        "process_original_message": False,
        "skill": "notes",
        "skill_action": "create",
        "message": "Saved.",
        "instructions": ["Store the supplied notes."],
        "notes": [
            {"content": "Book the dentist", "note_date": "2026-09-08", "tags": ["health"]},
            {"content": "Try the new database index", "note_date": None, "tags": ["idea"]},
        ],
    }


def main() -> int:
    for module in (classify_client, _load_router_classify()):
        normalized = module.normalize_plan(_note_plan(), "remember these", "Asia/Ho_Chi_Minh")
        assert normalized["task_hint"] == "note"
        assert normalized["skill"] == "notes"
        assert normalized["notes"][0]["note_date"] == "2026-09-08"
        assert normalized["notes"][1]["note_date"] is None
        assert normalized["notes"][0]["tags"] == ["health"]
    assert classify_client.plan_is_note(classify_client.normalize_plan(
        _note_plan(), "remember these", "Asia/Ho_Chi_Minh"
    ))

    cancel = classify_client.normalize_plan(
        {
            "task_hint": "control",
            "task_type": "cancel_task",
            "skill": "task-control",
            "skill_action": "cancel",
            "process_original_message": False,
            "message": "Stop it.",
            "instructions": ["Cancel active work."],
            "cancel_selector": {"message_id": "quoted-7"},
        },
        "stop the current request",
        "Asia/Ho_Chi_Minh",
    )
    assert classify_client.plan_is_cancel_task(cancel)
    assert cancel["cancel_selector"] == {"message_id": "quoted-7"}

    assert notes_client.note_scope(thread_id="dm-thread", thread_type="user", sender_id="u1") == "zalo:user:u1"
    assert notes_client.note_scope(thread_id="g1", thread_type="group", sender_id="u1") == "zalo:group:g1"

    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(method: str, path: str, payload=None):
        calls.append((method, path, payload))
        if path == "/v1/notes/query":
            return {"success": True, "items": [{"id": "note_1", "content": "Book the dentist", "note_date": "2026-09-08"}]}
        return {"success": True, "note": {"id": f"note_{len(calls)}"}}

    with patch.object(notes_client, "_request", side_effect=fake_request):
        result = notes_client.execute_note_plan(
            _note_plan(), thread_id="dm-thread", thread_type="user", sender_id="u1"
        )
        assert result["success"] and result["count"] == 2
        assert calls[0][2]["scope_id"] == "zalo:user:u1"

        lookup = dict(_note_plan())
        lookup.update({"skill_action": "lookup", "notes": [], "note_selector": {"query": "dentist"}})
        result = notes_client.execute_note_plan(
            lookup, thread_id="dm-thread", thread_type="user", sender_id="u1"
        )
        assert result["count"] == 1 and "Book the dentist" in result["text"]

    memory_source = (ROOT / "architect" / "memory" / "memory-manager" / "app.py").read_text(encoding="utf-8")
    adapter_source = (ZALO / "adapter.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS notes" in memory_source
    assert "notes_scope_date_idx" in memory_source and "notes_fts_idx" in memory_source
    assert "CREATE TABLE IF NOT EXISTS note_audit" in memory_source
    assert "fallback_clauses = date_clauses" in memory_source
    assert "Control-plane cancellation bypasses rate limits and FIFO admission" in adapter_source
    assert "except asyncio.CancelledError:" in adapter_source
    assert "self._as_active_turn_tasks" in adapter_source
    print("OK notes/control unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
