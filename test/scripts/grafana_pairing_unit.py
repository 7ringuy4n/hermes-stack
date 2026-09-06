# -*- coding: utf-8 -*-
"""Local unit: Grafana pairs Prometheus with OmniRoute and host exporters."""
from __future__ import annotations

import io
import json
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

    dashboard_root = ROOT / "config" / "monitor" / "grafana" / "dashboards" / "json"
    overview = (dashboard_root / "assistant-overview.json").read_text(encoding="utf-8")
    for expr in ("assistant_service_up", "omnirouter_scrape_success"):
        if expr not in overview:
            print(f"FAIL overview dashboard missing {expr}")
            fails += 1
        else:
            print(f"PASS dashboard expr {expr}")

    identities: list[tuple[str, str, str]] = []
    for dashboard in sorted(dashboard_root.glob("*.json")):
        payload = json.loads(dashboard.read_text(encoding="utf-8"))
        identities.append((dashboard.name, str(payload.get("uid") or ""), str(payload.get("title") or "")))
    uids = [item[1] for item in identities]
    titles = [item[2] for item in identities]
    if any(not uid or not title for _, uid, title in identities):
        print("FAIL Grafana dashboard missing uid or title")
        fails += 1
    elif len(uids) != len(set(uids)) or len(titles) != len(set(titles)):
        print("FAIL duplicate Grafana dashboard uid or title")
        fails += 1
    else:
        print(f"PASS {len(identities)} Grafana dashboards have unique uid and title")

    legacy = ROOT / "architect" / "monitor" / "grafana"
    if legacy.exists() and any(path.is_file() for path in legacy.rglob("*")):
        print("FAIL duplicate architect/monitor/grafana provisioning tree remains")
        fails += 1
    else:
        print("PASS one canonical Grafana provisioning tree")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
