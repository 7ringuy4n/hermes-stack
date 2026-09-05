# -*- coding: utf-8 -*-
"""Local unit: Grafana pairs Prometheus with OmniRoute and host exporters."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    fails = 0
    compose = (ROOT / "docker" / "docker-compose.security.yml").read_text(encoding="utf-8")
    if "build: ./architect/monitor/router-exporter" not in compose:
        print("FAIL compose Omni exporter does not use router-exporter")
        fails += 1
    else:
        print("PASS compose Omni exporter uses router-exporter")

    prom = (ROOT / "config" / "monitor" / "prometheus.yml").read_text(encoding="utf-8")
    for job in ("omni-exporter", "node-exporter", "stack-exporter"):
        if f"job_name: {job}" not in prom:
            print(f"FAIL prometheus.yml missing job {job}")
            fails += 1
        else:
            print(f"PASS prometheus job {job}")

    overview = (
        ROOT / "architect" / "monitor" / "grafana" / "dashboards" / "json" / "assistant-overview.json"
    ).read_text(encoding="utf-8")
    for expr in ("assistant_service_up", "omnirouter_scrape_success"):
        if expr not in overview:
            print(f"FAIL overview dashboard missing {expr}")
            fails += 1
        else:
            print(f"PASS dashboard expr {expr}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
