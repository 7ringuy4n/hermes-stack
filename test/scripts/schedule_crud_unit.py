# -*- coding: utf-8 -*-
"""Unit: shared cron promote + schedule CRUD parse (no docker)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "backup-restore" / "lib"))
sys.path.insert(0, str(ROOT / "architect" / "zalo-api"))

from hermes_cron_share import promote_shared_cron  # noqa: E402
from schedule_crud import (  # noqa: E402
    apply_schedule_update,
    fmt_show,
    jobs_for_thread,
    new_job,
    parse_hhmm_cron,
    parse_update_args,
    resolve_job,
    split_add_args,
    take_all_flag,
    visible_jobs,
)
from schedule_list import schedule_clock_label, schedule_row_label  # noqa: E402


def test_promote(tmp: Path) -> None:
    replica = tmp / "replicas" / "oldcid" / "cron"
    replica.mkdir(parents=True)
    payload = {
        "jobs": [
            {"id": "abc123abc123", "name": "wakeup", "prompt": "send prices", "schedule": {"kind": "cron", "expr": "0 6 * * *"}},
            {"id": "deadbeef0001", "name": "daily-optimize-rules-memory", "prompt": "internal"},
        ],
        "updated_at": "2026-08-18T00:00:00+07:00",
    }
    (replica / "jobs.json").write_text(json.dumps(payload), encoding="utf-8")
    result = promote_shared_cron(tmp)
    assert result["action"] == "promoted", result
    shared = json.loads((tmp / "cron" / "jobs.json").read_text(encoding="utf-8"))
    assert len(shared["jobs"]) == 2
    again = promote_shared_cron(tmp)
    assert again["action"] == "keep_shared", again
    print("PASS promote replica jobs.json to shared cron")


def test_parse() -> None:
    assert parse_hhmm_cron("6:00") == "0 6 * * *"
    assert parse_hhmm_cron("18:30") == "30 18 * * *"
    assert parse_hhmm_cron("6h") == "0 6 * * *"
    assert parse_hhmm_cron("6h sáng") == "0 6 * * *"
    expr, name, prompt = split_add_args("6:00 Gửi giá xăng")
    assert expr == "0 6 * * *" and "xăng" in prompt
    expr, name, prompt = split_add_args("0 7 * * * Morning brief")
    assert expr == "0 7 * * *" and "Morning" in prompt
    print("PASS parse add args")


def test_update_colon_payload() -> None:
    jobs = [
        new_job(
            prompt="old wakeup only",
            expr="0 6 * * *",
            name="Nhắc dậy đi làm 6h sáng",
        )
    ]
    rest = (
        "Nhắc dậy đi làm 6h sáng : 1. Send daily message to wakeup every in DM/group: "
        "* a 6:00 AM GMT +7\n"
        "\t2. Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế\n"
        "\t3. Cập nhật ngắn gọn nội dung giá xăng E5 RON92 và E10 RON95 gần nhất"
    )
    job, expr, prompt, err = parse_update_args(rest, jobs)
    assert err == "", err
    assert job is not None and job.get("name") == "Nhắc dậy đi làm 6h sáng"
    assert expr is None
    assert prompt.startswith("1. Send daily")
    assert "E10 RON95" in prompt
    job, expr, prompt, err = parse_update_args("1 --time 7:00", jobs)
    assert err == "" and expr == "0 7 * * *" and prompt == ""
    job, expr, prompt, err = parse_update_args("1 --timer 12:35", jobs)
    assert err == "" and expr == "35 12 * * *" and prompt == ""
    job, expr, prompt, err = parse_update_args("1 -- Gửi giá xăng", jobs)
    assert err == "" and "xăng" in prompt and expr is None
    job, expr, prompt, err = parse_update_args("1 : timer 11:50", jobs)
    assert err == "" and expr == "50 11 * * *" and prompt == ""
    job, expr, prompt, err = parse_update_args("1 : 11:50", jobs)
    assert err == "" and expr == "50 11 * * *" and prompt == ""
    expr, name, prompt = split_add_args("timer 11:50 Gửi giá xăng")
    assert expr == "50 11 * * *" and "xăng" in prompt
    print("PASS update colon payload + --time + -- prompt")


def test_crud_visible() -> None:
    jobs = [
        new_job(prompt="Gửi giá xăng", expr="0 6 * * *", name="wakeup"),
        {"id": "x", "name": "daily-optimize-rules-memory", "prompt": "x", "schedule": {"kind": "cron", "expr": "0 0 * * *"}},
    ]
    vis = visible_jobs(jobs)
    assert len(vis) == 1, vis
    assert vis[0].get("no_agent") is True
    job, err = resolve_job(jobs, "1")
    assert err == "" and job and job.get("name") == "wakeup"
    print("PASS visible + resolve index")


def test_thread_scope() -> None:
    dm = new_job(prompt="dm wakeup", expr="0 6 * * *", name="dm-job", sender="u1", thread="u1")
    grp = new_job(prompt="group brief", expr="0 7 * * *", name="grp-job", sender="u1", thread="g9")
    jobs = [dm, grp]
    assert [j["name"] for j in jobs_for_thread(jobs, "u1")] == ["dm-job"]
    assert [j["name"] for j in jobs_for_thread(jobs, "g9")] == ["grp-job"]
    job, err = resolve_job(jobs_for_thread(jobs, "u1"), "1")
    assert err == "" and job and job.get("name") == "dm-job"
    job, err = resolve_job(jobs_for_thread(jobs, "g9"), "1")
    assert err == "" and job and job.get("name") == "grp-job"
    want_all, sel = take_all_flag("all 2 --time 7:00")
    assert want_all is True and sel.startswith("2")
    want_all, sel = take_all_flag("")
    assert want_all is False and sel == ""
    job, err = resolve_job(jobs, "")
    assert err and job is None
    print("PASS thread scope + list all flag")


def test_timer_flag_and_clock_label() -> None:
    job = new_job(prompt="timer 11:50", expr="0 6 * * *", name="buoi-sang-hcm")
    parsed, expr, prompt, err = parse_update_args("1 --timer 12:35", [job])
    assert err == "" and expr == "35 12 * * *" and prompt == ""
    apply_schedule_update(parsed, expr, prompt)
    assert parsed.get("prompt") == ""
    assert parsed.get("next_run_at") is None
    label = schedule_row_label(parsed) or ""
    assert "12:35" in label, label
    assert "kind" not in label and "timer 11:50" not in label, label
    shown = fmt_show(parsed)
    assert "12:35" in shown and "timer 11:50" not in shown
    assert "Chưa có nội dung" in shown
    assert schedule_clock_label({"kind": "cron", "expr": "35 12 * * *"}) == "12:35"
    print("PASS timer flag + clock label")


def main() -> int:
    fails = 0
    try:
        with tempfile.TemporaryDirectory() as td:
            test_promote(Path(td))
        test_parse()
        test_update_colon_payload()
        test_crud_visible()
        test_thread_scope()
        test_timer_flag_and_clock_label()
    except AssertionError as e:
        print(f"FAIL {e}")
        fails = 1
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
