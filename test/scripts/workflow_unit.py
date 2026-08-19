# -*- coding: utf-8 -*-
"""Unit: generic workflow manager (memory store, no docker)."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "workflow"))
sys.path.insert(0, str(ROOT / "test" / "scripts"))

from manager import COMPLETED, DEAD, RUNNING, WorkflowManager, next_daily_cron  # noqa: E402
from plan import extract_cron_expr, plan_instructions  # noqa: E402
from store import MemoryStore  # noqa: E402
from classify_fixtures import install_unit_planner  # noqa: E402

install_unit_planner()


def test_plan() -> None:
    parts = plan_instructions(
        "Thực hiện: 1. Tìm giá USD hiện tại 2. Vẽ hình HCM 3. Cập nhật giá xăng"
    )
    assert len(parts) == 3 and "USD" in parts[0] and "xăng" in parts[2], parts
    en4 = plan_instructions(
        "1. Send a hello greeting message.\n"
        "2. Draw an image of Ho Chi Minh City based on the actual current weather.\n"
        "3. Give a brief update of the latest E5 RON92 and E10 RON95 gasoline prices, in Vietnamese.\n"
        "4. Draw a video of Ho Chi Minh City based on the actual current weather."
    )
    assert len(en4) == 4 and "hello" in en4[0].lower() and "video" in en4[3].lower(), en4
    from classify_fixtures import FIXTURE_INFOGRAPHIC_VI, FIXTURE_INFOGRAPHIC_DAILY  # noqa: E402

    poster = plan_instructions(FIXTURE_INFOGRAPHIC_VI)
    assert len(poster) == 1 and "E10 RON95" in poster[0] and "thời tiết" in poster[0], poster
    daily = plan_instructions(FIXTURE_INFOGRAPHIC_DAILY)
    assert len(daily) == 1 and "E5 RON92" in daily[0], daily
    cron = extract_cron_expr("hằng ngày lúc 06:00 GMT+7")
    assert cron == "0 6 * * *", cron
    print("PASS plan_instructions + cron extract")


def test_three_jobs_complete() -> None:
    mgr = WorkflowManager(MemoryStore())
    wf = mgr.create(
        ["alpha", "beta", "gamma"],
        context={"execute": "record_only"},
        wrap=False,
    )
    assert len(wf["jobs"]) == 3
    mgr.dispatch_outbox()
    seen = []
    for _ in range(3):
        job = mgr.claim("w1", execute="record_only")
        assert job, "expected a job"
        seen.append(job["instruction"])
        mgr.dispatch_outbox()
        mgr.complete(job["id"], {"ok": True})
        mgr.dispatch_outbox()
    wf = mgr.get_workflow(wf["id"])
    assert wf["status"] == "COMPLETED", wf["status"]
    assert seen == ["alpha", "beta", "gamma"], seen
    print("PASS sequential 3 jobs → COMPLETED")


def test_parallel_jobs_all_queued() -> None:
    mgr = WorkflowManager(MemoryStore())
    wf = mgr.create(
        ["alpha", "beta", "gamma"],
        context={"execute": "record_only"},
        wrap=False,
        sequential=False,
    )
    jobs = wf["jobs"]
    assert len(jobs) == 3
    assert all(not (j.get("dependencies") or []) for j in jobs), jobs
    assert all(j["status"] == "QUEUED" for j in jobs), [j["status"] for j in jobs]
    mgr.dispatch_outbox()
    seen = []
    for _ in range(3):
        job = mgr.claim("w1", execute="record_only")
        assert job, f"expected parallel job, got {seen}"
        seen.append(job["instruction"])
    assert sorted(seen) == ["alpha", "beta", "gamma"], seen
    print("PASS parallel 3 jobs no deps")


def test_partial_failure_and_no_rerun() -> None:
    mgr = WorkflowManager(MemoryStore(), lease_s=30)
    wf = mgr.create(["ok-a", "fail-b", "ok-c"], context={"execute": "record_only"}, wrap=False)
    mgr.dispatch_outbox()
    a = mgr.claim("w1", execute="record_only")
    mgr.complete(a["id"], {"ok": True})
    mgr.dispatch_outbox()
    b = mgr.claim("w1", execute="record_only")
    for _ in range(5):
        mgr.fail(b["id"], "boom")
        mgr.dispatch_outbox()
        nxt = mgr.claim("w1", execute="record_only")
        if not nxt:
            break
        b = nxt
        if b["status"] == "DEAD":
            break
    wf = mgr.get_workflow(wf["id"])
    jobs = {j["instruction"]: j["status"] for j in wf["jobs"]}
    assert jobs["ok-a"] == COMPLETED
    assert jobs["fail-b"] == DEAD
    # job c stays PENDING because it depends on b
    assert jobs["ok-c"] in {"PENDING", DEAD}
    assert wf["status"] in {"PARTIAL_FAILURE", "RUNNING", "FAILED"}
    print("PASS fail job independently (no rerun of completed)")


def test_idempotency_and_stale_lease() -> None:
    mgr = WorkflowManager(MemoryStore(), lease_s=1)
    wf1 = mgr.create(["only"], idempotency_prefix="sch1:2026-08-18", wrap=False)
    wf2 = mgr.create(["only"], idempotency_prefix="sch1:2026-08-18", wrap=False)
    assert wf1["id"] == wf2["id"]
    mgr.dispatch_outbox()
    job = mgr.claim("w1", execute="hermes")
    assert job
    job["lease_until"] = datetime.now(timezone.utc) - timedelta(seconds=10)
    mgr.store.update_job(job["id"], lease_until=job["lease_until"], status=RUNNING)
    n = mgr.recover_stale()
    assert n == 1
    mgr.dispatch_outbox()
    again = mgr.claim("w2", execute="hermes")
    assert again and again["id"] == job["id"]
    print("PASS idempotency + stale lease requeue")


def test_schedule_tick_creates_jobs() -> None:
    mgr = WorkflowManager(MemoryStore())
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    sch = mgr.upsert_schedule(
        cron_expr="0 6 * * *",
        text="1. wakeup 2. image 3. fuel",
        name="morning",
        context={"execute": "record_only"},
        cadence="daily",
    )
    mgr.store.update_schedule(sch["id"], next_run_at=past)
    ids = mgr.fire_due_schedules()
    assert len(ids) == 1
    wf = mgr.get_workflow(ids[0])
    assert len(wf["jobs"]) == 3
    ids2 = mgr.fire_due_schedules()
    assert ids2 == [] or ids2[0] == ids[0]
    print("PASS schedule tick → 3 jobs, no duplicate same window")


def test_once_schedule_refire_same_day() -> None:
    mgr = WorkflowManager(MemoryStore())
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    sch = mgr.upsert_schedule(
        cron_expr="0 8 * * *",
        text="1. wakeup 2. image 3. fuel",
        name="once-lab",
        schedule_id="case25_once",
        context={"execute": "record_only", "plan": {"ok": True, "instructions": ["a", "b", "c"]}},
        cadence="once",
        next_run_at=past,
    )
    ids1 = mgr.fire_due_schedules()
    assert len(ids1) == 1, ids1
    assert mgr.store.get_schedule("case25_once") is None, mgr.store.get_schedule("case25_once")
    sch2 = mgr.upsert_schedule(
        cron_expr="1 8 * * *",
        text="1. wakeup 2. image 3. fuel",
        name="once-lab-2",
        schedule_id="case25_once",
        context={"execute": "record_only", "plan": {"ok": True, "instructions": ["a", "b", "c"]}},
        cadence="once",
        next_run_at=past,
    )
    ids2 = mgr.fire_due_schedules()
    assert len(ids2) == 1, ids2
    assert ids2[0] != ids1[0], (ids1, ids2)
    print("PASS once cadence re-fire same day creates a new workflow")


def test_timezone_default_gmt7() -> None:
    now = datetime(2026, 8, 18, 22, 30, tzinfo=timezone.utc)
    nxt = next_daily_cron("0 6 * * *", "Asia/Ho_Chi_Minh", now)
    local = nxt.astimezone(timezone(timedelta(hours=7)))
    assert (local.hour, local.minute) == (6, 0), local.isoformat()
    assert local.date().isoformat() == "2026-08-19", local.isoformat()
    print("PASS schedule timezone Asia/Ho_Chi_Minh (GMT+7)")


def test_same_minute_grace_1354() -> None:
    tz = timezone(timedelta(hours=7))
    created = datetime(2026, 8, 18, 13, 54, 20, tzinfo=tz)
    nxt = next_daily_cron("54 13 * * *", "Asia/Ho_Chi_Minh", created)
    local = nxt.astimezone(tz)
    assert local.date().isoformat() == "2026-08-18", local.isoformat()
    assert (local.hour, local.minute) == (13, 54)
    later = datetime(2026, 8, 18, 13, 57, 0, tzinfo=tz)
    nxt2 = next_daily_cron("54 13 * * *", "Asia/Ho_Chi_Minh", later)
    local2 = nxt2.astimezone(tz)
    assert local2.date().isoformat() == "2026-08-19", local2.isoformat()
    print("PASS 13:54 GMT+7 same-minute grace (today); 13:57 → tomorrow")


def main() -> int:
    try:
        test_plan()
        test_three_jobs_complete()
        test_parallel_jobs_all_queued()
        test_partial_failure_and_no_rerun()
        test_idempotency_and_stale_lease()
        test_schedule_tick_creates_jobs()
        test_once_schedule_refire_same_day()
        test_timezone_default_gmt7()
        test_same_minute_grace_1354()
    except AssertionError as e:
        print(f"FAIL {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
