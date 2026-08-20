# -*- coding: utf-8 -*-
"""Copy user lịch from jobs.json into the workflow service; mark jobs no_agent.

Run on the VPS host (127.0.0.1:8108). Does not print secrets. Does not send Zalo.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = "http://127.0.0.1:8108"
JOBS = Path("/data/assistant/cron/jobs.json")
_INTERNAL = re.compile(
    r"daily[-_]?optimize|optimize[-_]?rules|new.?session|rotate.?session|clearsession",
    re.I,
)


def _req(method: str, path: str, payload=None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        return {"ok": False, "error": body or str(e.code)}


def _expr(job: dict) -> str:
    sch = job.get("schedule")
    if isinstance(sch, dict):
        expr = str(sch.get("expr") or "")
        if expr:
            return expr
        run_at = str(sch.get("run_at") or "").strip()
        if run_at:
            try:
                dt = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
            except ValueError:
                return ""
            return f"{dt.minute} {dt.hour} * * *"
    return str(job.get("schedule_display") or job.get("cron") or "")


def _once_next_run(job: dict) -> str:
    sch = job.get("schedule")
    if not isinstance(sch, dict):
        return ""
    if str(sch.get("kind") or "").lower() != "once":
        return ""
    return str(sch.get("run_at") or "").strip()


def main() -> int:
    try:
        h = _req("GET", "/health")
    except (urllib.error.URLError, TimeoutError):
        print("FAIL workflow unreachable")
        return 1
    if not h.get("ok"):
        print("FAIL workflow health")
        return 1
    if not JOBS.is_file():
        print("PASS migrate skipped (no jobs.json)")
        return 0
    try:
        data = json.loads(JOBS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("FAIL jobs.json unreadable")
        return 1
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        print("PASS migrate skipped (empty)")
        return 0
    n = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        jid = str(job.get("id") or "")
        name = str(job.get("name") or "")
        prompt = str(job.get("prompt") or "").strip()
        expr = _expr(job)
        if not jid or not prompt or not expr:
            continue
        if _INTERNAL.search(name) or _INTERNAL.search(prompt):
            continue
        origin = job.get("origin") if isinstance(job.get("origin"), dict) else {}
        tid = str(origin.get("thread_id") or origin.get("chat_id") or "")
        once_at = _once_next_run(job)
        if once_at:
            # Never replay leftover once jobs into the live ticker.
            job["no_agent"] = True
            n += 1
            continue
        if "::job::" in tid:
            continue
        body = {
            "id": jid,
            "name": name or jid,
            "cron_expr": expr,
            "timezone": "Asia/Ho_Chi_Minh",
            "text": prompt,
            "origin": origin,
            "context": {
                "thread_id": tid,
                "thread_type": str(origin.get("thread_type") or "user"),
                "chat_type": str(origin.get("chat_type") or "dm"),
                "sender_id": str(origin.get("user_id") or ""),
                "sender_name": str(origin.get("chat_name") or tid),
                "execute": "hermes",
            },
            "enabled": True,
        }
        if once_at:
            body["cadence"] = "once"
            body["next_run_at"] = once_at
        try:
            out = _req("POST", "/v1/schedules", body)
        except (urllib.error.URLError, TimeoutError):
            print("FAIL upsert")
            return 1
        if not out.get("ok"):
            print("FAIL upsert", jid[:12], (out.get("error") or out)[:200])
            continue
        job["no_agent"] = True
        n += 1
    JOBS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS migrate n={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
