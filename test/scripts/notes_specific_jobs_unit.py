# -*- coding: utf-8 -*-
"""Unit: search-then-note listing policy is skill-owned; host stays structural."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from notes_persist import (  # noqa: E402
    keep_search_then_note_atomic,
    load_search_then_note_contract,
    notes_from_assistant_body,
    plan_wants_persist_gathered_notes,
    should_defer_note_persist,
)


def main() -> int:
    print("running test case 1/7")
    plan = {
        "ok": True,
        "task_hint": "search",
        "skill": "web_search",
        "process_original_message": True,
        "persist_gathered_notes": True,
    }
    assert plan_wants_persist_gathered_notes(plan)
    assert should_defer_note_persist(plan, "any language user ask")
    assert keep_search_then_note_atomic(plan)

    print("running test case 2/7")
    assert not should_defer_note_persist(
        {"task_hint": "search", "skill": "web_search", "persist_gathered_notes": False},
        "tim tin fullstack roi note lai",
    )

    print("running test case 3/7")
    body = (
        "1. Fullstack Developer (Nexacro / Front End / Java) — Hitachi Digital Services\n"
        "2. Backend Engineer — Zalopay (ITviec, HCM)\n\n"
        "https://www.topcv.vn/viec-lam/hitachi\n"
        "https://itviec.com/it-jobs/zalopay\n"
    )
    notes = notes_from_assistant_body(body, timezone="Asia/Ho_Chi_Minh")
    assert len(notes) == 2, notes
    assert all("http" in n["content"].lower() for n in notes)

    print("running test case 4/7")
    # Host persists numbered rows structurally; skill owns skipping aggregates.
    mixed = notes_from_assistant_body(
        "1. Fullstack Developer tại HCM (~41 tin)\n"
        "2. Fullstack Developer (Nexacro / Front End / Java) — Hitachi Digital Services\n"
        "https://example.com/h\n"
    )
    assert len(mixed) == 2

    print("running test case 5/7")
    contract = load_search_then_note_contract(
        prior_notes=["Fullstack Developer (Nexacro / Front End / Java) — Hitachi Digital Services"]
    )
    assert "Hitachi" in contract
    assert "Prior notes" in contract
    assert "aggregate" in contract.lower() or "count" in contract.lower()

    print("running test case 6/7")
    skill = (ROOT / "hermes" / "main" / "skills" / "notes" / "SKILL.md").read_text(encoding="utf-8")
    assert "persist_gathered_notes" in skill
    assert "Title (stack) — Employer" in skill
    prompt = (
        ROOT / "hermes" / "main" / "skills" / "notes" / "prompts" / "search_then_note_listing.txt"
    ).read_text(encoding="utf-8")
    assert "{{PRIOR_NOTES}}" in prompt
    classify = (ROOT / "hermes" / "main" / "skills" / "classify" / "parts" / "notes.txt").read_text(
        encoding="utf-8"
    )
    assert "persist_gathered_notes true" in classify

    print("running test case 7/7")
    persist_src = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "notes_persist.py").read_text(
        encoding="utf-8"
    )
    assert "tuyển dụng" not in persist_src.lower()
    assert "~41 tin" not in persist_src
    assert "_JOB_ASK_RE" not in persist_src
    assert "_AGGREGATE_COUNT_RE" not in persist_src
    assert "_NOTE_AFTER_SEARCH_RE" not in persist_src

    print("notes_specific_jobs_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
