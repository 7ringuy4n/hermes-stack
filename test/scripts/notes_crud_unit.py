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
            "title": payload.get("title"),
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
            haystack = f"{note.get('title') or ''} {note.get('content') or ''}".lower()
            if payload.get("date_from") and str(note.get("note_date") or "") < payload["date_from"]:
                continue
            if payload.get("date_to") and str(note.get("note_date") or "") > payload["date_to"]:
                continue
            if q and q not in haystack and not any(q in t for t in (note.get("tags") or [])):
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
        if "title" in payload:
            note["title"] = payload.get("title")
        return {"success": True, "note": note}
    if method == "DELETE":
        nid = path.rsplit("/", 1)[-1].split("?", 1)[0]
        if nid in STORE:
            STORE.pop(nid)
            return {"success": True}
        return {"success": False, "error": "not_found"}
    return {"success": False, "error": "unhandled"}


def main() -> int:
    print("running test case 1/10 create with model titles")
    STORE.clear()
    with patch.object(notes_client, "_request", side_effect=fake_request):
        created = notes_client.execute_note_plan(
            {
                "skill_action": "create",
                "notes": [
                    {"title": "Buy milk", "content": "CRUD-A buy milk", "note_date": "2026-09-11", "tags": ["errand"]},
                    {"title": "Java indexing idea", "content": "CRUD-B java idea", "note_date": "2026-09-11", "tags": ["java"]},
                ],
            },
            thread_id="u1",
            thread_type="user",
            sender_id="u1",
        )
        assert created["success"] and created["count"] == 2

        assert STORE["note_1"]["title"] == "Buy milk"

        print("running test case 2/10 clean list")
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
        assert "Java indexing idea" in looked["text"] and "CRUD-B" not in looked["text"]

        print("running test case 3/10 detail view")
        detailed = notes_client.execute_note_plan(
            {"skill_action": "lookup", "note_selector": {"query": "java", "view": "detail"}},
            thread_id="u1", thread_type="user", sender_id="u1",
        )
        assert "Java indexing idea" in detailed["text"] and "CRUD-B java idea" in detailed["text"]

        print("running test case 4/10 update")
        nid = looked["items"][0]["id"]
        updated = notes_client.execute_note_plan(
            {
                "skill_action": "update",
                "note_selector": {"id": nid},
                "notes": [{"title": "Revised Java idea", "content": "CRUD-B java idea revised", "note_date": "2026-09-11", "tags": ["java"]}],
            },
            thread_id="u1",
            thread_type="user",
            sender_id="u1",
        )
        assert updated["success"]
        assert STORE[nid]["content"] == "CRUD-B java idea revised"
        assert STORE[nid]["title"] == "Revised Java idea"

        print("running test case 5/10 ambiguous")
        STORE["note_extra"] = {
            "id": "note_extra",
            "title": "Java twin",
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

        print("running test case 6/10 date-range bulk update")
        bulk_update = notes_client.execute_note_plan(
            {
                "skill_action": "update",
                "note_selector": {"date_from": "2026-09-11", "date_to": "2026-09-11", "bulk": True},
                "notes": [{"title": "Archived item", "content": "Archived 2026-09-11 item", "note_date": "2026-09-11", "tags": ["archive"]}],
            },
            thread_id="u1", thread_type="user", sender_id="u1",
        )
        assert bulk_update["success"] and bulk_update["count"] == 3

        print("running test case 7/10 delete specific")
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

        print("running test case 8/10 delete all")
        deleted_all = notes_client.execute_note_plan(
            {"skill_action": "delete", "note_selector": {"match_all": True, "bulk": True}},
            thread_id="u1", thread_type="user", sender_id="u1",
        )
        assert deleted_all["success"] and deleted_all["count"] == 2 and not STORE

        print("running test case 9/10 count view")
        counted = notes_client.execute_note_plan(
            {"skill_action": "lookup", "note_selector": {"match_all": True, "view": "count"}},
            thread_id="u1", thread_type="user", sender_id="u1",
        )
        assert counted["text"] == "0 note(s)."

        print("running test case 10/10 scope isolation marker")
        assert notes_client.note_scope(thread_id="g1", thread_type="group", sender_id="u1") == "zalo:group:g1"
        assert notes_client.note_scope(thread_id="u1", thread_type="user", sender_id="u1") == "zalo:user:u1"

    print("notes_crud_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
