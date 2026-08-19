# -*- coding: utf-8 -*-
"""Unit: plenty-in-one-message + same-time vs different-time crons for Zalo and Hermes.

No docker. Covers the 13:54 GMT+7 same-minute catch-up miss.
"""
from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "workflow"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))
sys.path.insert(0, str(ROOT / "architect" / "gateway" / "api-gateway"))
sys.path.insert(0, str(ROOT / "test" / "scripts"))

from manager import WorkflowManager, next_daily_cron  # noqa: E402
from plan import extract_cron_expr, plan_instructions  # noqa: E402
from store import MemoryStore  # noqa: E402

from multi_request import looks_like_schedule_job, split_compound_requests  # noqa: E402

import app as gateway  # noqa: E402
from classify_fixtures import install_unit_planner  # noqa: E402

install_unit_planner()

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TZ = "Asia/Ho_Chi_Minh"
GMT7 = ZoneInfo(TZ)

PLENTY_NOW = (
    "Thực hiện:\n"
    "1. Gửi tin chào buổi sáng\n"
    "2. Vẽ hình thời tiết HCMC\n"
    "3. Cập nhật giá xăng E5 RON92 và E10 RON95\n"
    "4. Báo tỷ giá USD/VND\n"
    "5. Tóm tắt lịch hôm nay\n"
    "6. Nhắc uống nước"
)

PLENTY_CRON_1354 = (
    "hằng ngày lúc 13:54 GMT+7:\n"
    "1. Send daily wakeup in DM/group: * a 6:00 AM GMT +7\n"
    "2. Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế\n"
    "3. Cập nhật giá xăng E5 RON92 và E10 RON95\n"
    "4. Báo tỷ giá USD/VND\n"
    "5. Tóm tắt lịch hôm nay\n"
    "6. Nhắc uống nước"
)

PLENTY_CRON_0600 = (
    "hằng ngày lúc 06:00 GMT+7:\n"
    "1. wakeup\n"
    "2. HCMC weather image\n"
    "3. fuel prices\n"
    "4. USD rate\n"
    "5. calendar brief\n"
    "6. water reminder"
)

PLENTY_CRON_1200 = (
    "hằng ngày lúc 12:00 GMT+7:\n"
    "1. noon ping\n"
    "2. HCMC weather image\n"
    "3. fuel prices\n"
    "4. USD rate\n"
    "5. calendar brief\n"
    "6. water reminder"
)


def _local(h: int, m: int, s: int = 0, day: int = 18) -> datetime:
    return datetime(2026, 8, day, h, m, s, tzinfo=GMT7)


def _drain(mgr: WorkflowManager, execute: str, n: int) -> list[str]:
    seen: list[str] = []
    mgr.dispatch_outbox()
    for _ in range(n):
        job = mgr.claim("w1", execute=execute)
        if not job:
            break
        seen.append(str(job.get("instruction") or ""))
        mgr.complete(job["id"], {"ok": True, "execute": execute})
        mgr.dispatch_outbox()
    return seen


def test_plenty_immediate_zalo_and_hermes() -> None:
    zalo_parts = split_compound_requests(PLENTY_NOW)
    assert len(zalo_parts) == 6, zalo_parts
    assert "xăng" in zalo_parts[2] and "USD" in zalo_parts[3]
    hermes_parts = gateway._plan_instructions(PLENTY_NOW)
    assert hermes_parts == plan_instructions(PLENTY_NOW)
    assert len(hermes_parts) == 6
    wf_parts = plan_instructions(PLENTY_NOW)
    assert len(wf_parts) == 6
    print("PASS plenty immediate: Zalo split + Hermes plan + workflow plan = 6")


def test_plenty_schedule_kept_whole_then_explodes() -> None:
    assert looks_like_schedule_job(PLENTY_CRON_1354)
    assert split_compound_requests(PLENTY_CRON_1354) == [PLENTY_CRON_1354]
    assert gateway._looks_like_schedule(PLENTY_CRON_1354)
    parts = plan_instructions(PLENTY_CRON_1354)
    assert len(parts) == 6, parts
    print("PASS plenty schedule stays one inbound blob, explodes to 6 jobs")


def test_extract_1354_not_body_0600() -> None:
    expr = extract_cron_expr(PLENTY_CRON_1354)
    assert expr == "54 13 * * *", expr
    assert extract_cron_expr("13:54 GMT+7") == "54 13 * * *"
    print("PASS extract 13:54 GMT+7 (not body 6:00 AM)")


def test_same_minute_1354_is_due_today() -> None:
    created = _local(13, 54, 20)
    nxt = next_daily_cron("54 13 * * *", TZ, created)
    local = nxt.astimezone(GMT7)
    assert (local.hour, local.minute) == (13, 54), local.isoformat()
    assert local.date() == created.date(), local.isoformat()
    mgr = WorkflowManager(MemoryStore())
    sch = mgr.upsert_schedule(
        cron_expr="54 13 * * *",
        text=PLENTY_CRON_1354,
        name="zalo-1354",
        tz_name=TZ,
        origin={"platform": "zalo", "thread_id": "u-zalo"},
        context={"execute": "hermes", "thread_id": "u-zalo"},
        schedule_id="sch_zalo_1354",
        cadence="daily",
        next_run_at=nxt,
    )
    ids = mgr.fire_due_schedules(created)
    assert len(ids) == 1, ids
    wf = mgr.get_workflow(ids[0])
    assert len(wf["jobs"]) == 6, len(wf["jobs"])
    assert (sch.get("origin") or {}).get("platform") == "zalo"
    print("PASS 13:54 GMT+7 created at 13:54:20 still fires today (6 jobs)")


def test_same_time_two_channels() -> None:
    now = _local(6, 0, 5)
    mgr = WorkflowManager(MemoryStore())
    due = now - timedelta(seconds=5)
    mgr.upsert_schedule(
        cron_expr="0 6 * * *",
        text=PLENTY_CRON_0600,
        name="zalo-am",
        origin={"platform": "zalo", "thread_id": "z1"},
        context={"execute": "hermes", "thread_id": "z1", "sender_id": "z-user"},
        schedule_id="sch_zalo_0600",
        cadence="daily",
        next_run_at=due,
    )
    mgr.upsert_schedule(
        cron_expr="0 6 * * *",
        text=PLENTY_CRON_0600,
        name="hermes-am",
        origin={"platform": "hermes-api", "path": "/v1/chat/completions"},
        context={"execute": "hermes_http", "model": "gpt-test"},
        schedule_id="sch_hermes_0600",
        cadence="daily",
        next_run_at=due,
    )
    ids = mgr.fire_due_schedules(now)
    assert len(set(ids)) == 2, ids
    zalo_wf = hermes_wf = None
    for wid in ids:
        wf = mgr.get_workflow(wid)
        assert len(wf["jobs"]) == 6
        plat = str((wf.get("origin") or {}).get("platform") or "")
        exe = str((wf["jobs"][0].get("context") or {}).get("execute") or "")
        if plat == "zalo":
            zalo_wf = wf
            assert exe == "hermes"
        elif plat == "hermes-api":
            hermes_wf = wf
            assert exe == "hermes_http"
    assert zalo_wf and hermes_wf
    zalo_ids = {j["id"] for j in zalo_wf["jobs"]}
    hermes_ids = {j["id"] for j in hermes_wf["jobs"]}
    assert not zalo_ids.intersection(hermes_ids)
    again = mgr.fire_due_schedules(now)
    assert again == [] or set(again).issubset(set(ids))
    seen_z = _drain(mgr, "hermes", 6)
    seen_h = _drain(mgr, "hermes_http", 6)
    assert len(seen_z) == 6 and len(seen_h) == 6, (len(seen_z), len(seen_h), seen_z[:1], seen_h[:1])
    assert mgr.get_workflow(zalo_wf["id"])["status"] == "COMPLETED"
    assert mgr.get_workflow(hermes_wf["id"])["status"] == "COMPLETED"
    print("PASS same-time 06:00: Zalo + Hermes, 6 jobs each, no cross-talk")


def test_different_time_independent() -> None:
    mgr = WorkflowManager(MemoryStore())
    at_0605 = _local(6, 0, 5)
    at_1205 = _local(12, 0, 5)
    mgr.upsert_schedule(
        cron_expr="0 6 * * *",
        text=PLENTY_CRON_0600,
        name="zalo-0600",
        origin={"platform": "zalo", "thread_id": "z-morning"},
        context={"execute": "hermes", "thread_id": "z-morning"},
        schedule_id="sch_diff_0600",
        cadence="daily",
        next_run_at=_local(6, 0, 0),
    )
    mgr.upsert_schedule(
        cron_expr="0 12 * * *",
        text=PLENTY_CRON_1200,
        name="hermes-1200",
        origin={"platform": "hermes-api"},
        context={"execute": "hermes_http"},
        schedule_id="sch_diff_1200",
        cadence="daily",
        next_run_at=_local(12, 0, 0),
    )
    morning = mgr.fire_due_schedules(at_0605)
    assert len(morning) == 1
    am = mgr.get_workflow(morning[0])
    assert (am.get("origin") or {}).get("platform") == "zalo"
    assert len(am["jobs"]) == 6
    noon = mgr.fire_due_schedules(at_1205)
    assert len(noon) == 1
    pm = mgr.get_workflow(noon[0])
    assert (pm.get("origin") or {}).get("platform") == "hermes-api"
    assert len(pm["jobs"]) == 6
    assert morning[0] != noon[0]
    print("PASS different-time 06:00 vs 12:00 fire independently")


def test_two_zalo_users_same_clock() -> None:
    now = _local(13, 54, 8)
    mgr = WorkflowManager(MemoryStore())
    due = _local(13, 54, 0)
    for uid in ("u-a", "u-b"):
        mgr.upsert_schedule(
            cron_expr="54 13 * * *",
            text=PLENTY_CRON_1354,
            name=f"zalo-{uid}",
            origin={"platform": "zalo", "thread_id": uid, "user_id": uid},
            context={"execute": "hermes", "thread_id": uid, "sender_id": uid},
            schedule_id=f"sch_{uid}_1354",
            cadence="daily",
            next_run_at=due,
        )
    ids = mgr.fire_due_schedules(now)
    assert len(set(ids)) == 2, ids
    threads = set()
    for wid in ids:
        wf = mgr.get_workflow(wid)
        assert len(wf["jobs"]) == 6
        threads.add(str((wf.get("origin") or {}).get("thread_id") or ""))
    assert threads == {"u-a", "u-b"}
    print("PASS two Zalo users same 13:54 clock, isolated 6-job workflows")


def test_reupsert_keeps_due_past_next_run() -> None:
    mgr = WorkflowManager(MemoryStore())
    due = _local(13, 54, 0)
    mgr.upsert_schedule(
        cron_expr="54 13 * * *",
        text=PLENTY_CRON_1354,
        name="keep-due",
        schedule_id="sch_keep_due",
        cadence="daily",
        next_run_at=due,
    )
    later = _local(13, 55, 0)
    again = mgr.upsert_schedule(
        cron_expr="54 13 * * *",
        text=PLENTY_CRON_1354,
        name="keep-due",
        schedule_id="sch_keep_due",
        cadence="daily",
    )
    nxt = again.get("next_run_at")
    assert nxt is not None
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=timezone.utc)
    assert nxt <= later.astimezone(timezone.utc)
    ids = mgr.fire_due_schedules(later)
    assert len(ids) == 1
    print("PASS re-upsert same clock keeps past next_run so catch-up still fires")


def test_missed_today_when_next_run_already_tomorrow() -> None:
    mgr = WorkflowManager(MemoryStore())
    tomorrow = _local(13, 54, 0, day=19)
    mgr.upsert_schedule(
        cron_expr="54 13 * * *",
        text=PLENTY_CRON_1354,
        name="missed-1354",
        origin={"platform": "zalo", "thread_id": "u-miss"},
        context={"execute": "hermes", "thread_id": "u-miss"},
        schedule_id="sch_missed_1354",
        cadence="daily",
        next_run_at=tomorrow,
    )
    ids = mgr.fire_due_schedules(_local(13, 55, 0, day=18))
    assert len(ids) == 1, ids
    wf = mgr.get_workflow(ids[0])
    assert len(wf["jobs"]) == 6
    print("PASS missed 13:54 still fires today even if next_run jumped to tomorrow")


def main() -> int:
    try:
        test_plenty_immediate_zalo_and_hermes()
        test_plenty_schedule_kept_whole_then_explodes()
        test_extract_1354_not_body_0600()
        test_same_minute_1354_is_due_today()
        test_same_time_two_channels()
        test_different_time_independent()
        test_two_zalo_users_same_clock()
        test_reupsert_keeps_due_past_next_run()
        test_missed_today_when_next_run_already_tomorrow()
    except AssertionError as e:
        print(f"FAIL {e}")
        return 1
    print("PASS workflow schedule concurrency (Zalo + Hermes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
