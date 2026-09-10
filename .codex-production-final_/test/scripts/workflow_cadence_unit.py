# -*- coding: utf-8 -*-
"""Unit: schedule cadence (once / daily / weekly / monthly / yearly)."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "workflow"))

from manager import WorkflowManager, next_run_after  # noqa: E402
from plan import extract_cadence  # noqa: E402
from store import MemoryStore  # noqa: E402

TZ = "Asia/Ho_Chi_Minh"
GMT7 = ZoneInfo(TZ)


def test_extract() -> None:
    from classify_client import set_planner  # noqa: E402

    def schedule_plan(cadence: str):
        def planner(text, **k):
            del text, k
            return {
                "task_hint": "schedule",
                "cadence": cadence,
                "cron_expr": "0 6 * * *",
                "instructions": ["hello"],
            }

        return planner

    try:
        for kind in ("once", "daily", "weekly", "monthly", "yearly"):
            set_planner(schedule_plan(kind))
            assert extract_cadence("unused") == kind
        set_planner(lambda text, **k: {"task_hint": "unknown", "instructions": ["x"]})
        assert extract_cadence("hằng ngày lúc 06:00 GMT+7") == "once"
        assert extract_cadence("weekly at 09:00") == "once"
    finally:
        set_planner(None)
    print("PASS extract_cadence")


def test_once_deletes() -> None:
    mgr = WorkflowManager(MemoryStore())
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    sch = mgr.upsert_schedule(
        cron_expr="9 18 * * *",
        text="đặt lịch chạy lúc 18:09\n1. hello",
        name="once",
    )
    assert sch.get("cadence") == "once"
    mgr.store.update_schedule(sch["id"], next_run_at=past)
    ids = mgr.fire_due_schedules()
    assert len(ids) == 1
    assert mgr.store.get_schedule(sch["id"]) is None
    print("PASS once cadence deletes after fire")


def test_weekly_next() -> None:
    now = datetime(2026, 8, 18, 18, 10, tzinfo=GMT7)
    nxt = next_run_after("weekly", "9 18 * * *", TZ, now)
    assert nxt is not None
    local = nxt.astimezone(GMT7)
    assert local.date().isoformat() == "2026-08-25"
    assert (local.hour, local.minute) == (18, 9)
    print("PASS weekly +7 days")


def main() -> int:
    try:
        test_extract()
        test_once_deletes()
        test_weekly_next()
    except AssertionError as e:
        print(f"FAIL {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
