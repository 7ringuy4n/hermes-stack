# -*- coding: utf-8 -*-
"""Live VPS checks for the workflow service (127.0.0.1:8108). No secrets."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "http://127.0.0.1:8108"

PLENTY = (
    "1. wakeup-record 2. image-record 3. fuel-record "
    "4. usd-record 5. calendar-record 6. water-record"
)


def _req(method: str, path: str, payload=None, timeout: float = 8.0) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    r = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _wait_completed(wid: str, tries: int = 80) -> str:
    status = ""
    for _ in range(tries):
        time.sleep(0.25)
        got = _req("GET", f"/v1/workflows/{wid}")
        status = str((got.get("workflow") or {}).get("status") or "")
        if status == "COMPLETED":
            break
    return status


def main() -> int:
    fails = 0
    try:
        h = _req("GET", "/health")
        if not h.get("ok"):
            print("FAIL health", h)
            return 1
        print("PASS health")
    except (urllib.error.URLError, TimeoutError) as e:
        print("FAIL health unreachable", type(e).__name__)
        return 1

    created = _req(
        "POST",
        "/v1/workflows",
        {
            "instructions": ["alpha-record", "beta-record", "gamma-record"],
            "context": {"execute": "record_only"},
            "wrap": False,
            "sequential": True,
        },
    )
    wf = created.get("workflow") or {}
    wid = str(wf.get("id") or "")
    if not wid or len(wf.get("jobs") or []) != 3:
        print("FAIL create", created)
        return 1
    print("PASS create 3 jobs")

    status = _wait_completed(wid)
    if status != "COMPLETED":
        print("FAIL drain status", status)
        fails += 1
    else:
        print("PASS record_only drain COMPLETED")

    text_wf = _req(
        "POST",
        "/v1/workflows",
        {
            "text": "Thực hiện: 1. USD check 2. HCMC image 3. fuel prices "
            "4. calendar 5. water 6. ping",
            "context": {"execute": "record_only"},
            "wrap": True,
        },
    )
    jobs = (text_wf.get("workflow") or {}).get("jobs") or []
    if len(jobs) != 6:
        print("FAIL plan from text", len(jobs), text_wf)
        fails += 1
    else:
        print("PASS plan text → 6 jobs")
        _wait_completed(str((text_wf.get("workflow") or {}).get("id") or ""))

    listed = _req("GET", "/v1/schedules")
    if not listed.get("ok"):
        print("FAIL list schedules", listed)
        fails += 1
    else:
        print("PASS list schedules")

    sch = _req(
        "POST",
        "/v1/schedules",
        {
            "id": "vps_record_sched",
            "name": "vps-record",
            "time": "06:00 GMT+7",
            "text": PLENTY,
            "context": {"execute": "record_only"},
        },
    )
    if not sch.get("ok") or not (sch.get("schedule") or {}).get("id"):
        print("FAIL upsert schedule", sch)
        fails += 1
    else:
        print("PASS upsert schedule")
        _req("DELETE", "/v1/schedules/vps_record_sched")

    past = (datetime.now(timezone.utc) - timedelta(seconds=8)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    test_ids = ("vps_zalo_same", "vps_hermes_same", "vps_later_clock")
    for sid in test_ids:
        _req("DELETE", f"/v1/schedules/{sid}")
    zalo = _req(
        "POST",
        "/v1/schedules",
        {
            "id": "vps_zalo_same",
            "name": "vps-zalo-same",
            "cron_expr": "0 6 * * *",
            "text": PLENTY,
            "origin": {"platform": "zalo", "thread_id": "vps-zalo", "test": "case24"},
            "context": {"execute": "record_only", "thread_id": "vps-zalo"},
            "next_run_at": past,
        },
    )
    hermes = _req(
        "POST",
        "/v1/schedules",
        {
            "id": "vps_hermes_same",
            "name": "vps-hermes-same",
            "cron_expr": "0 6 * * *",
            "text": PLENTY,
            "origin": {"platform": "hermes-api", "test": "case24"},
            "context": {"execute": "record_only"},
            "next_run_at": past,
        },
    )
    later = _req(
        "POST",
        "/v1/schedules",
        {
            "id": "vps_later_clock",
            "name": "vps-later",
            "cron_expr": "0 12 * * *",
            "text": PLENTY,
            "origin": {"platform": "hermes-api", "test": "case24-later"},
            "context": {"execute": "record_only"},
            "next_run_at": future,
        },
    )
    if not (zalo.get("ok") and hermes.get("ok") and later.get("ok")):
        print("FAIL upsert same/different clocks", zalo, hermes, later)
        fails += 1
    else:
        ticked = _req("POST", "/v1/schedules/tick")
        wids = ticked.get("workflows") or []
        fired = []
        for wid2 in wids:
            got = _req("GET", f"/v1/workflows/{wid2}")
            wf2 = got.get("workflow") or {}
            origin = wf2.get("origin") if isinstance(wf2.get("origin"), dict) else {}
            if str(origin.get("test") or "") != "case24":
                continue
            plat = str(origin.get("platform") or "")
            njob = len(wf2.get("jobs") or [])
            fired.append((plat, njob, str(wf2.get("id") or "")))
            if njob != 6:
                print("FAIL tick jobs", plat, njob)
                fails += 1
            st = _wait_completed(str(wf2.get("id") or ""))
            if st != "COMPLETED":
                print("FAIL tick drain", plat, st)
                fails += 1
        plats = {p for p, _n, _i in fired}
        if "zalo" not in plats or "hermes-api" not in plats:
            print("FAIL same-time tick channels", fired)
            fails += 1
        else:
            print("PASS same-time tick Zalo + Hermes plenty jobs")
        later_row = _req("GET", "/v1/schedules")
        later_keep = [
            s
            for s in (later_row.get("schedules") or [])
            if str(s.get("id") or "") == "vps_later_clock"
        ]
        if not later_keep or later_keep[0].get("last_fired_at"):
            print("FAIL different-time later schedule should not fire", later_keep)
            fails += 1
        else:
            print("PASS different-time future clock did not fire")
        for sid in test_ids:
            _req("DELETE", f"/v1/schedules/{sid}")

    waited = _req("POST", f"/v1/workflows/{wid}/wait", {"timeout_s": 2})
    if not waited.get("ok"):
        print("FAIL wait route", waited)
        fails += 1
    else:
        print("PASS wait route")

    if fails:
        return 1
    print("PASS workflow vps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
