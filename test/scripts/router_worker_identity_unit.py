#!/usr/bin/env python3
"""Unit: Router Worker has one canonical live identity."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker" / "docker-compose.yml"
ALLOWED_LEGACY_FILES = {
    ROOT / "scripts" / "main" / "cleanup-obsolete-env.py",
    ROOT / "scripts" / "main" / "openbao_common.py",
    ROOT / "architect" / "backup-restore" / "lib" / "workers.sh",
    Path(__file__).resolve(),
    ROOT / "test" / "scripts" / "openbao_common_unit.py",
}
SKIP_FILES = {
    ROOT / "AGENT_RULES.md",  # operator-owned local policy may be ahead of the branch
    ROOT / "test" / "SETUP.local.md",
}
SKIP_PARTS = {".git", ".idea", "history", "reports", "__pycache__"}
LEGACY_MARKERS = (
    "model-router",
    "model_router",
    "MODEL_ROUTER",
    "Model Router",
    "model router",
)


def main() -> int:
    compose = COMPOSE.read_text(encoding="utf-8")
    required = (
        "router-worker:",
        "container_name: router-worker",
        "build: ./architect/models/router-worker",
        "ROUTER_WORKER_URL",
        "http://router-worker:8096",
    )
    failed = False
    for marker in required:
        if marker not in compose:
            print(f"FAIL canonical compose marker missing: {marker}")
            failed = True

    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path in ALLOWED_LEGACY_FILES or path in SKIP_FILES:
            continue
        if path.name in {"CHANGELOG.md", "HISTORY.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found = [marker for marker in LEGACY_MARKERS if marker in text]
        if found:
            print(f"FAIL retired live identity in {path.relative_to(ROOT)}: {', '.join(found)}")
            failed = True

    if failed:
        return 1
    print("OK router-worker canonical identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
