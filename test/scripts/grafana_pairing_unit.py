# -*- coding: utf-8 -*-
"""Local unit: Grafana pairing files mention required exporters and 9router TCP target."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    fails = 0
    workers = (ROOT / "architect" / "backup-restore" / "lib" / "workers.sh").read_text(
        encoding="utf-8"
    )
    nine_default_off = (
        'ENABLE_9ROUTER="${ENABLE_9ROUTER:-inactive}"' in workers
        or 'ENABLE_9ROUTER="${ENABLE_9ROUTER:-0}"' in workers
    )
    compose = (ROOT / "docker" / "docker-compose.security.yml").read_text(encoding="utf-8")
    if "9router=9router:20128" not in compose:
        if nine_default_off:
            print("PASS compose HEALTH_TARGETS omits 9router (ENABLE_9ROUTER default 0)")
        else:
            print("FAIL compose HEALTH_TARGETS missing 9router TCP")
            fails += 1
    else:
        print("PASS compose HEALTH_TARGETS includes 9router")

    prom = (ROOT / "config" / "monitor" / "prometheus.yml").read_text(encoding="utf-8")
    for job in ("nine-exporter", "omni-exporter", "node-exporter", "stack-exporter"):
        if f"job_name: {job}" not in prom:
            print(f"FAIL prometheus.yml missing job {job}")
            fails += 1
        else:
            print(f"PASS prometheus job {job}")

    exporter = (ROOT / "architect" / "monitor" / "stack-exporter" / "app.py").read_text(encoding="utf-8")
    if '"9router"' not in exporter:
        print("FAIL stack-exporter does not special-case 9router TCP")
        fails += 1
    else:
        print("PASS stack-exporter 9router TCP")

    overview = (
        ROOT / "architect" / "monitor" / "grafana" / "dashboards" / "json" / "assistant-overview.json"
    ).read_text(encoding="utf-8")
    for expr in ("assistant_service_up", "n9router_scrape_success", "omnirouter_scrape_success"):
        if expr not in overview:
            print(f"FAIL overview dashboard missing {expr}")
            fails += 1
        else:
            print(f"PASS dashboard expr {expr}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
