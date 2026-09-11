# -*- coding: utf-8 -*-
"""Unit: deferred search-then-note persist + lookup query simplify."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from notes_persist import (  # noqa: E402
    notes_from_assistant_body,
    plan_is_empty_note_create,
    should_defer_note_persist,
    simplify_note_query,
    strip_false_note_claims,
    text_wants_search_then_note,
)
import notes_client  # noqa: E402


def main() -> int:
    print("running test case 1/8")
    assert plan_is_empty_note_create(
        {
            "task_hint": "note",
            "skill": "notes",
            "skill_action": "create",
            "notes": [],
        }
    )
    assert not plan_is_empty_note_create(
        {
            "task_hint": "note",
            "skill": "notes",
            "skill_action": "create",
            "notes": [{"content": "hello", "note_date": None, "tags": []}],
        }
    )

    print("running test case 2/8")
    ask = "tim them cac tin tuyen dung Java BE fullstack moi tren facebook sau do note lai"
    assert text_wants_search_then_note(ask)
    assert should_defer_note_persist({"task_hint": "search", "skill": "web_search"}, ask)
    assert should_defer_note_persist(
        {"task_hint": "note", "skill": "notes", "skill_action": "create", "notes": []},
        ask,
    )

    print("running test case 3/8")
    body = (
        "Day la cac tin:\n"
        "1. Vinsmart Future — TechLead Backend (Golang/Java) tai HCM\n"
        "2. Du an Java + ReactJS Ha Noi luong 45 trieu\n"
        "3. ITviec fullstack React .NET HCM\n\n"
        "Da luu thanh ghi chu (ngay 2026-09-11): cac tin tuyen dung.\n"
        "Ban co muon loc theo khu vuc khong?"
    )
    cleaned = strip_false_note_claims(body)
    assert "Da luu thanh ghi chu" not in cleaned
    notes = notes_from_assistant_body(body, user_ask=ask, timezone="Asia/Ho_Chi_Minh")
    assert len(notes) == 3, notes
    assert "Vinsmart" in notes[0]["content"]
    assert "java" in notes[0]["tags"]
    assert notes[0]["note_date"]

    print("running test case 4/8")
    simplified = simplify_note_query("hien thi cac tin tuyen dung java da luu")
    assert simplified.lower() == "java", simplified
    assert "java" in simplify_note_query("hiển thị các tin tuyển dụng java đã lưu").lower()

    print("running test case 5/8")
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(method: str, path: str, payload=None):
        calls.append((method, path, payload))
        if path == "/v1/notes/query":
            q = str((payload or {}).get("query") or "")
            if "java" in q.lower() and "hien thi" not in q.lower() and "hiển" not in q.lower():
                return {
                    "success": True,
                    "items": [
                        {
                            "id": "note_j",
                            "content": "Vinsmart Future TechLead Backend Java",
                            "note_date": "2026-09-11",
                        }
                    ],
                }
            return {"success": True, "items": []}
        return {"success": True, "note": {"id": "note_x"}}

    with patch.object(notes_client, "_request", side_effect=fake_request):
        lookup = {
            "skill_action": "lookup",
            "notes": [],
            "note_selector": {"query": "hien thi cac tin tuyen dung java da luu"},
        }
        result = notes_client.execute_note_plan(
            lookup, thread_id="dm", thread_type="user", sender_id="u1"
        )
        assert result["success"] and result["count"] == 1, result
        assert "Vinsmart" in result["text"]

    print("running test case 6/8")
    with patch.object(notes_client, "_request", side_effect=fake_request):
        create_plan = {
            "skill_action": "create",
            "notes": notes,
        }
        created = notes_client.execute_note_plan(
            create_plan, thread_id="dm", thread_type="user", sender_id="u1"
        )
        assert created["success"] and created["count"] == 3
        assert any(c[0] == "POST" and c[1] == "/v1/notes" for c in calls)

    print("running test case 7/8")
    adapter = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    assert "defer persist after gather" in adapter
    assert "_as_persist_deferred_notes" in adapter
    assert "deferred note persist" in adapter
    assert "real_thread_id" in adapter

    print("running test case 8/8")
    # Pending is keyed by the real Zalo thread, not the ::job:: session id.
    from turn_wait import real_thread_id  # noqa: E402

    bare = "233767886566872937"
    iso = f"{bare}::job::job_abc"
    assert real_thread_id(iso) == bare

    print("notes_deferred_persist_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
