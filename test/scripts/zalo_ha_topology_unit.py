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
        "promoted owner scans durable queue registry": (
            "_as_queue_recovery_loop" in adapter
            and "_as_resume_stale_owner_queues" in adapter
            and "queue_active_ids" in adapter
            and "queue_recover" in adapter
            and "store.worker_done(thread_id)" in adapter
        ),
        "worker lease exceeds queued turn deadline": (
            "def _as_queue_worker_ttl_s" in adapter
            and "self._as_queue_turn_timeout_s() + 60.0" in adapter
            and "store.worker_try(tid, worker_ttl)" in adapter
            and "store.worker_touch(tid, worker_ttl)" in adapter
        ),
        "lease loss cancels owner-local work": (
            "_as_cancel_owner_work()" in adapter
            and "_as_active_turn_tasks" in adapter
            and 'tasks.add(getattr(self, "_sse_task", None))' in adapter
            and 'tasks.add(getattr(self, "_as_workflow_task", None))' in adapter
            and "task.cancel()" in adapter
        ),
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
