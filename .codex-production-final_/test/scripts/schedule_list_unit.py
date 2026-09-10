# -*- coding: utf-8 -*-
"""Unit: Hermes cron list formatter (no docker)."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "zalo-api"))

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from schedule_list import fmt_hermes_cron_list  # noqa: E402


def main() -> int:
    fails = 0

    empty = fmt_hermes_cron_list("")
    if "trống" not in empty.lower():
        print(f"FAIL empty: {empty!r}")
        fails += 1
    else:
        print("PASS empty")

    internal = fmt_hermes_cron_list(
        "job1 daily-optimize-rules-memory 0 0 * * *\njob2 wakeup-daily 0 6 * * * send prices"
    )
    if "daily-optimize" in internal.lower():
        print(f"FAIL internal filter: {internal!r}")
        fails += 1
    elif "wakeup" not in internal.lower():
        print(f"FAIL kept user job: {internal!r}")
        fails += 1
    else:
        print("PASS internal filter")

    payload = json.dumps(
        [
            {"name": "morning-brief", "schedule": "0 6 * * *", "message": "1. wakeup 2. prices"},
            {"name": "daily-optimize-rules-memory", "schedule": "0 0 * * *"},
        ]
    )
    parsed = fmt_hermes_cron_list(payload)
    if "morning-brief" not in parsed or "optimize" in parsed.lower():
        print(f"FAIL json parse: {parsed!r}")
        fails += 1
    else:
        print("PASS json parse")

    dict_sched = fmt_hermes_cron_list(
        json.dumps(
            [
                {
                    "name": "buoi-sang-hcm",
                    "schedule": {"kind": "cron", "expr": "35 12 * * *", "display": "35 12 * * *"},
                    "prompt": "timer 11:50",
                }
            ]
        )
    )
    if "12:35" not in dict_sched or "kind" in dict_sched or "timer 11:50" in dict_sched:
        print(f"FAIL dict schedule label: {dict_sched!r}")
        fails += 1
    else:
        print("PASS dict schedule label")

    scoped = fmt_hermes_cron_list(payload, heading="lịch chat này")
    if not scoped.startswith("lịch chat này"):
        print(f"FAIL heading: {scoped!r}")
        fails += 1
    else:
        print("PASS heading")

    capped = fmt_hermes_cron_list(
        "\n".join(f"job-{i} 0 {i} * * * task" for i in range(5)),
        limit=2,
    )
    if "còn 3" not in capped:
        print(f"FAIL cap: {capped!r}")
        fails += 1
    else:
        print("PASS cap")

    empty_cli = fmt_hermes_cron_list(
        "No scheduled jobs.\nCreate one with 'hermes cron create ...'"
    )
    if "trống" not in empty_cli.lower() or "lịch" not in empty_cli.lower():
        print(f"FAIL empty cli: {empty_cli!r}")
        fails += 1
    else:
        print("PASS empty cli")

    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
