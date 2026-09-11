# -*- coding: utf-8 -*-
"""Unit: atomic search-then-note + citation URLs in deferred notes."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from notes_persist import (  # noqa: E402
    keep_search_then_note_atomic,
    notes_from_assistant_body,
    should_defer_note_persist,
    strip_false_note_claims,
)
from multi_request import parts_from_plan  # noqa: E402
import notes_client  # noqa: E402


def main() -> int:
    print("running test case 1/8")
    ask = "truy cap cac nhom facebook, ITviec, TopCV tim tin fullstack BE Java o HCM roi note lai"
    plan = {
        "ok": True,
        "task_hint": "search",
        "instructions": [
            "Search public Facebook groups, ITviec, TopCV for Java fullstack HCM jobs",
            "Note the findings",
        ],
    }
    assert should_defer_note_persist(plan, ask)
    assert keep_search_then_note_atomic(plan, ask)
    assert parts_from_plan(ask, plan) == [ask]

    print("running test case 2/8")
    body = (
        "Ket qua:\n"
        "1. Fullstack Developer (Java) — AI POWER (TopCV, HCM)\n"
        "2. Backend Engineer — Zalopay (ITviec, HCM)\n"
        "3. Java Backend — DOSOFTPRO (TopDev)\n\n"
        "https://www.topcv.vn/tim-viec-lam-java-tai-ho-chi-minh-kl2\n"
        "https://itviec.com/viec-lam-it/back-end\n"
        "https://topdev.vn/jobs/search?keyword=Java\n\n"
        "Da luu ghi chu\n"
        "Ban co muon loc them khong?"
    )
    cleaned = strip_false_note_claims(body)
    assert "Da luu ghi chu" not in cleaned
    notes = notes_from_assistant_body(body, user_ask=ask, timezone="Asia/Ho_Chi_Minh")
    assert len(notes) == 3, notes
    assert all("http" in n["content"].lower() for n in notes), notes
    assert "topcv" in notes[0]["content"].lower() or "Nguồn:" in notes[0]["content"]
    assert notes[0].get("metadata", {}).get("citations")

    print("running test case 3/8")
    dirty = (
        "1. Java Engineer — Elcom (TopCV) Minh khong the tu luu note tu day, "
        "nen chua xac nhan duoc viec note.\n"
        "https://www.topcv.vn/viec-lam/elcom"
    )
    notes2 = notes_from_assistant_body(dirty, user_ask=ask)
    assert len(notes2) == 1
    assert "khong the tu luu" not in notes2[0]["content"].lower()
    assert "http" in notes2[0]["content"].lower()

    print("running test case 4/8")
    # Unrelated multi-instruction must still split.
    other = {
        "ok": True,
        "task_hint": "normal",
        "instructions": ["Gui thoi tiet HCM", "Gui gia xang"],
    }
    parts = parts_from_plan("Gui thoi tiet HCM roi gia xang", other)
    assert len(parts) == 2

    print("running test case 5/8")
    calls = []

    def fake_request(method, path, payload=None):
        calls.append((method, path, payload))
        return {"success": True, "note": {"id": "note_x", "content": payload.get("content")}}

    with patch.object(notes_client, "_request", side_effect=fake_request):
        created = notes_client.execute_note_plan(
            {"skill_action": "create", "notes": notes},
            thread_id="u1",
            thread_type="user",
            sender_id="u1",
        )
        assert created["success"] and created["count"] == 3
        meta = calls[0][2].get("metadata") or {}
        assert meta.get("citations") or "http" in str(calls[0][2].get("content") or "")

    print("running test case 6/8")
    adapter = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    assert "keep_search_then_note_atomic" in adapter
    mr = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "multi_request.py").read_text(
        encoding="utf-8"
    )
    assert "keep_search_then_note_atomic" in mr

    print("running test case 7/8")
    skill = (ROOT / "hermes" / "main" / "skills" / "classify" / "parts" / "notes.txt").read_text(
        encoding="utf-8"
    )
    assert "single task_hint=search" in skill or "one instruction" in skill
    assert "source URLs" in skill or "https" in skill

    print("running test case 8/8")
    rules = (ROOT / "test" / "RULES.md").read_text(encoding="utf-8")
    assert "search-then-note" in rules.lower() or "Search-then-note" in rules
    assert "citation" in rules.lower() or "URLs" in rules

    print("notes_atomic_cite_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
