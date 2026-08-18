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
    new_job,
    parse_hhmm_cron,
    resolve_job,
    split_add_args,
    visible_jobs,
)


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
    expr, name, prompt = split_add_args("6:00 Gửi giá xăng")
    assert expr == "0 6 * * *" and "xăng" in prompt
    expr, name, prompt = split_add_args("0 7 * * * Morning brief")
    assert expr == "0 7 * * *" and "Morning" in prompt
    print("PASS parse add args")


def test_crud_visible() -> None:
    jobs = [
        new_job(prompt="Gửi giá xăng", expr="0 6 * * *", name="wakeup"),
        {"id": "x", "name": "daily-optimize-rules-memory", "prompt": "x", "schedule": {"kind": "cron", "expr": "0 0 * * *"}},
    ]
    vis = visible_jobs(jobs)
    assert len(vis) == 1, vis
    job, err = resolve_job(jobs, "1")
    assert err == "" and job and job.get("name") == "wakeup"
    print("PASS visible + resolve index")


def main() -> int:
    fails = 0
    try:
        with tempfile.TemporaryDirectory() as td:
            test_promote(Path(td))
        test_parse()
        test_crud_visible()
    except AssertionError as e:
        print(f"FAIL {e}")
        fails = 1
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
