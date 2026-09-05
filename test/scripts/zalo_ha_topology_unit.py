#!/usr/bin/env python3
"""Static topology gate for Traefik-routed Zalo HA."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    compose = (ROOT / "docker/docker-compose.yml").read_text(encoding="utf-8")
    dynamic = (ROOT / "architect/edge/traefik/dynamic/hermes.yml").read_text(encoding="utf-8")
    entry = (ROOT / "hermes/main/docker/hermes-replica-entry.sh").read_text(encoding="utf-8")
    adapter = (ROOT / "hermes/main/plugins/zalo/adapter.py").read_text(encoding="utf-8")
    checks = {
        "Hermes uses internal Traefik bridge route": "http://traefik:8081/zalo-bridge" in compose,
        "Traefik routes bridge to proxy": 'url: "http://zalo-proxy:8787"' in dynamic,
        "Zalo route uses internal entrypoint": "zalo-internal" in dynamic,
        "Valkey lease config is injected": "ZALO_OWNER_LEASE_TTL_S" in compose,
        "adapter starts renewable lease": "_owner_lease_loop" in adapter and "lease.acquire()" in adapter,
        "filesystem owner election removed": "zalo_owner.lock" not in entry,
        "standby adapter is not disabled": 'export ZALO_PLUGIN_URL=""' not in entry,
        "standby continuously contends for the lease": (
            "standby acquired the bridge owner lease" in adapter
            and "while not self._stop:" in adapter
        ),
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
