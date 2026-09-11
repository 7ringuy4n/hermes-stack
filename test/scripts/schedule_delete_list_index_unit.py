# -*- coding: utf-8 -*-
"""Unit: quote-reply schedule delete by 1-based list_index + empty note fallthrough."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))
sys.path.insert(0, str(ROOT / "architect" / "models" / "router-worker"))

from classify_client import normalize_plan, plan_is_note  # noqa: E402
from schedule_client import (  # noqa: E402
    list_index_from_user_text,
    match_schedules_by_selector,
    quoted_looks_like_schedule_list,
    with_list_index_selector,
)


def _load_router_classify():
    sys.modules.setdefault("httpx", types.SimpleNamespace())
    path = ROOT / "architect" / "models" / "router-worker" / "classify.py"
    spec = importlib.util.spec_from_file_location("rw_schedule_delete_unit", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    xoa_so_2 = "xo\u00e1 s\u1ed1 2"
    xoa_lich_thu_2 = "xo\u00e1 l\u1ecbch th\u1ee9 2"
    xoa_accent = "x\u00f3a s\u1ed1 2"

    print("running test case 1/6")
    assert list_index_from_user_text(xoa_so_2) == 2
    assert list_index_from_user_text(xoa_lich_thu_2) == 2
    assert list_index_from_user_text(xoa_accent) == 2
    assert list_index_from_user_text("delete #3") == 3
    assert list_index_from_user_text("xem lich") is None

    print("running test case 2/6")
    quoted = (
        "l\u1ecbch (chat n\u00e0y + nh\u00f3m \u0111\u00e3 \u0111\u1eb7t) (2/2):\n"
        "1. weather @ 06:00 -> DM Tn\n"
        "2. case25-special-four @ 20:59 - hello"
    )
    assert quoted_looks_like_schedule_list(quoted)
    assert not quoted_looks_like_schedule_list("hello world")

    print("running test case 3/6")
    rows = [
        {"id": "a", "name": "weather", "fire_text": "weather"},
        {"id": "b", "name": "case25", "fire_text": "case25"},
    ]
    hits = match_schedules_by_selector(rows, {"list_index": 2})
    assert [r["id"] for r in hits] == ["b"], hits
    assert match_schedules_by_selector(rows, {"list_index": 9}) == []
    import schedule_client as sc

    assert callable(getattr(sc, "list_schedules", None))
    # list_schedules must exist for host delete/list; stub HTTP empty.
    from unittest.mock import patch

    with patch.object(sc, "_req", return_value={"schedules": rows}):
        assert [r["id"] for r in sc.list_schedules()] == ["a", "b"]
        assert [r["id"] for r in sc.schedules_for_thread("u1")] == []
        with_origin = [
            {
                "id": "a",
                "origin": {"thread_id": "u1", "user_id": "u1"},
                "context": {},
            },
            {
                "id": "b",
                "origin": {"thread_id": "u1"},
                "context": {},
            },
        ]
        with patch.object(sc, "_req", return_value={"schedules": with_origin}):
            assert [r["id"] for r in sc.schedules_for_thread("u1")] == ["a", "b"]


    print("running test case 4/6")
    sel = with_list_index_selector(None, xoa_so_2)
    assert sel and sel.get("list_index") == 2
    deleted = normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "delete_schedule",
            "skill": "schedule",
            "skill_action": "delete",
            "instructions": [xoa_so_2],
        },
        xoa_so_2,
        "Asia/Ho_Chi_Minh",
    )
    assert (deleted.get("schedule_selector") or {}).get("list_index") == 2, deleted

    print("running test case 5/6")
    rw = _load_router_classify()
    assert rw._list_index_from_user_text(xoa_lich_thu_2) == 2
    rw_deleted = rw.normalize_plan(
        {
            "task_hint": "schedule",
            "task_type": "delete_schedule",
            "skill": "schedule",
            "skill_action": "delete",
            "instructions": [xoa_lich_thu_2],
        },
        xoa_lich_thu_2,
        "Asia/Ho_Chi_Minh",
    )
    assert (rw_deleted.get("schedule_selector") or {}).get("list_index") == 2, rw_deleted

    print("running test case 6/6")
    empty_note = normalize_plan(
        {
            "task_hint": "note",
            "task_type": "note",
            "skill": "notes",
            "skill_action": "create",
            "instructions": ["find jobs then note"],
            "notes": [],
        },
        "tim tin tuyen dung fullstack roi note lai",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_is_note(empty_note)
    assert not (empty_note.get("notes") or [])
    adapter = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    assert "note create without notes[]" in adapter
    assert "quoted=quote_for_classify" in adapter

    print("schedule_delete_list_index_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
