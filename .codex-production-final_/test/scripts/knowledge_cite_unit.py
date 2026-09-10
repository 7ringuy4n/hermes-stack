# -*- coding: utf-8 -*-
"""Unit: knowledge-cite intercept follows LLM classify only."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))
sys.path.insert(0, str(ROOT / "test" / "scripts"))

from knowledge_cite import cite_query, plan_is_knowledge  # noqa: E402
from classify_fixtures import FIXTURE_ONCE_NOCITE, install_unit_planner  # noqa: E402
from classify_client import classify_text  # noqa: E402

install_unit_planner()


def main() -> int:
    once = classify_text(FIXTURE_ONCE_NOCITE)
    if plan_is_knowledge(once):
        print("FAIL once-lịch must not be knowledge")
        return 1
    if once.get("task_hint") != "schedule" or len(once.get("instructions") or []) != 3:
        print(f"FAIL expected schedule PLAN_N 3, got {once!r}")
        return 1
    cite = classify_text("cite labsolution")
    if not plan_is_knowledge(cite) or cite_query(cite) != "labsolution":
        print(f"FAIL cite command: {cite!r}")
        return 1
    catalog = classify_text("kiến thức đã học")
    if not plan_is_knowledge(catalog):
        print(f"FAIL catalog list: {catalog!r}")
        return 1
    if plan_is_knowledge({"ok": False, "error": "classify_llm_failed"}):
        print("FAIL failed classify must not cite-bypass Hermes")
        return 1
    print("knowledge_cite_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
