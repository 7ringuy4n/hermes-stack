# -*- coding: utf-8 -*-
"""Unit: note CRUD via notes_client (create/lookup/update/delete/ambiguous)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

import notes_client  # noqa: E402


STORE: dict[str, dict] = {}


def fake_request(method: str, path: str, payload=None):
    payload = payload or {}
    if method == "POST" and path == "/v1/notes":
        nid = f"note_{len(STORE)+1}"
        note = {
            "id": nid,
            "content": payload.get("content"),
            "note_date": payload.get("note_date"),
            "tags": list(payload.get("tags") or []),
            "scope_id": payload.get("scope_id"),
        }
        STORE[nid] = note
        return {"success": True, "note": note}
    if method == "POST" and path == "/v1/notes/query":
        q = str(payload.get("query") or "").lower()
        items = []
        for note in STORE.values():
            if payload.get("scope_id") and note.get("scope_id") != payload.get("scope_id"):
                continue
            if payload.get("id") and note.get("id") != payload.get("id"):
                continue
            content = str(note.get("content") or "").lower()
            if q and q not in content and not any(q in t for t in (note.get("tags") or [])):
                # date-only queries may be empty string
                if q:
                    continue
            items.append(note)
        if payload.get("id"):
            hit = STORE.get(str(payload.get("id")))
            items = [hit] if hit else []
        return {"success": True, "items": items, "count": len(items)}
    if method == "PATCH":
        nid = path.rsplit("/", 1)[-1]
        note = STORE.get(nid)
        if not note:
            return {"success": False, "error": "not_found"}
        if "content" in payload:
            note["content"] = payload.get("content")
        return {"success": True, "note": note}
    if method == "DELETE":
        nid = path.rsplit("/", 1)[-1].split("?", 1)[0]
        if nid in STORE:
            STORE.pop(nid)
            return {"success": True}
        return {"success": False, "error": "not_found"}
    return {"success": False, "error": "unhandled"}


def main() -> int:
    print("running test case 1/6 create")
    STORE.clear()
    with patch.object(notes_client, "_request", side_effect=fake_request):
        created = notes_client.execute_note_plan(
            {
                "skill_action": "create",
                "notes": [
                    {"content": "CRUD-A buy milk", "note_date": "2026-09-11", "tags": ["errand"]},
                    {"content": "CRUD-B java idea", "note_date": "2026-09-11", "tags": ["java"]},
                ],
            },
            thread_id="u1",
            thread_type="user",
            sender_id="u1",
        )
        assert created["success"] and created["count"] == 2

        print("running test case 2/6 lookup")
        looked = notes_client.execute_note_plan(
            {
                "skill_action": "lookup",
                "note_selector": {"query": "java"},
            },
            thread_id="u1",
            thread_type="user",
            sender_id="u1",
        )
        assert looked["success"] and looked["count"] == 1
        assert "CRUD-B" in looked["text"]

        print("running test case 3/6 update")
        nid = looked["items"][0]["id"]
        updated = notes_client.execute_note_plan(
            {
                "skill_action": "update",
                "note_selector": {"id": nid},
                "notes": [{"content": "CRUD-B java idea revised", "note_date": "2026-09-11", "tags": ["java"]}],
            },
            thread_id="u1",
            thread_type="user",
            sender_id="u1",
        )
        assert updated["success"]
        assert STORE[nid]["content"] == "CRUD-B java idea revised"

        print("running test case 4/6 ambiguous")
        STORE["note_extra"] = {
            "id": "note_extra",
            "content": "CRUD-B twin java",
            "note_date": "2026-09-11",
            "tags": ["java"],
            "scope_id": "zalo:user:u1",
        }
        amb = notes_client.execute_note_plan(
            {
                "skill_action": "update",
                "uncertain": True,
                "note_selector": {"query": "java"},
                "notes": [{"content": "should not write", "note_date": None, "tags": []}],
            },
            thread_id="u1",
            thread_type="user",
            sender_id="u1",
        )
        assert amb.get("success") is False and amb.get("error") == "ambiguous"

        print("running test case 5/6 delete")
        deleted = notes_client.execute_note_plan(
            {
                "skill_action": "delete",
                "note_selector": {"id": "note_1"},
            },
            thread_id="u1",
            thread_type="user",
            sender_id="u1",
        )
        assert deleted["success"]
        assert "note_1" not in STORE

        print("running test case 6/6 scope isolation marker")
        assert notes_client.note_scope(thread_id="g1", thread_type="group", sender_id="u1") == "zalo:group:g1"
        assert notes_client.note_scope(thread_id="u1", thread_type="user", sender_id="u1") == "zalo:user:u1"

    print("notes_crud_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
