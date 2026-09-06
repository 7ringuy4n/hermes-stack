#!/usr/bin/env python3
"""Static contract: duplicate cleanup preserves Compose scale slots."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    source = (ROOT / "architect" / "backup-restore" / "lib" / "workers.sh").read_text(
        encoding="utf-8"
    )
    function = source.split("assistant_rm_compose_recreate_orphans() {", 1)[1]
    function = function.split("assistant_remove_stale_worker_containers() {", 1)[0]
    assert 'com.docker.compose.container-number' in function
    assert 'key="${svc}:${slot}"' in function
    assert 'kept_slots[$key]' in function
    assert 'service=${svc} slot=${slot}' in function
    assert 'local id name project="${COMPOSE_PROJECT_NAME:-assistant}" svc kept' not in function
    print("OK compose scaled cleanup contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
