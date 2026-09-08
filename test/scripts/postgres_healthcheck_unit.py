#!/usr/bin/env python3
"""Unit: PostgreSQL readiness probes target the configured database."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    compose = (ROOT / "docker/docker-compose.yml").read_text(encoding="utf-8")
    backup = (ROOT / "architect/backup-restore/lib/backup.sh").read_text(
        encoding="utf-8"
    )
    expected = "pg_isready -U ${MEMORY_DB_USER:-hermes} -d ${MEMORY_DB_NAME:-hermes_memory}"
    assert expected in compose
    readiness_lines = [line.strip() for line in backup.splitlines() if "pg_isready" in line]
    assert len(readiness_lines) >= 3
    assert all("-d" in line and "MEMORY_DB_NAME" in line for line in readiness_lines)
    print("OK postgres_healthcheck_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
