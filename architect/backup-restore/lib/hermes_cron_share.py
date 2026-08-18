"""Durable Hermes schedule store: $HERMES_DATA_DIR/cron/jobs.json.

Jobs created in a replica home (`replicas/<container-id>/cron`) are lost on
destroy because container ids change and backup excludes `./replicas`.
Promote the newest jobs.json into the shared cron dir so list/CRUD/restore
share one file.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

JOBS_NAME = "jobs.json"
LOCK_SKIP = {".jobs.lock", ".tick.lock"}


def _jobs_path(cron_dir: Path) -> Path:
    return cron_dir / JOBS_NAME


def load_jobs_file(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size <= 0:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        jobs = data.get("jobs")
        return [j for j in jobs if isinstance(j, dict)] if isinstance(jobs, list) else []
    if isinstance(data, list):
        return [j for j in data if isinstance(j, dict)]
    return []


def dump_jobs_file(path: Path, jobs: list[dict[str, Any]], *, updated_at: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"jobs": jobs, "updated_at": updated_at}
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="jobs.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(raw)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def replica_job_files(data_dir: Path) -> list[Path]:
    root = data_dir / "replicas"
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.glob("*/cron/jobs.json"):
        if p.is_file() and p.stat().st_size > 0:
            out.append(p)
    return out


def newest_jobs_file(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return max(paths, key=lambda p: (p.stat().st_mtime, p.stat().st_size))


def promote_shared_cron(data_dir: str | Path) -> dict[str, Any]:
    """Copy newest replica jobs.json into data_dir/cron if shared is empty."""
    base = Path(data_dir)
    shared = base / "cron"
    shared.mkdir(parents=True, exist_ok=True)
    dest = _jobs_path(shared)
    shared_jobs = load_jobs_file(dest)
    candidates = replica_job_files(base)
    src = newest_jobs_file(candidates)
    if shared_jobs:
        return {
            "ok": True,
            "action": "keep_shared",
            "shared_jobs": len(shared_jobs),
            "replica_files": len(candidates),
        }
    if src is None:
        return {
            "ok": True,
            "action": "none",
            "shared_jobs": 0,
            "replica_files": 0,
        }
    jobs = load_jobs_file(src)
    if not jobs:
        return {
            "ok": True,
            "action": "none",
            "shared_jobs": 0,
            "replica_files": len(candidates),
        }
    src_dir = src.parent
    for item in src_dir.iterdir():
        if item.name in LOCK_SKIP or item.name.startswith(".fire-"):
            continue
        target = shared / item.name
        if item.is_dir():
            if target.exists() and not target.is_dir():
                target.unlink()
            shutil.copytree(item, target, dirs_exist_ok=True)
        elif item.is_file():
            shutil.copy2(item, target)
    return {
        "ok": True,
        "action": "promoted",
        "shared_jobs": len(load_jobs_file(dest)),
        "replica_files": len(candidates),
    }


def prune_stale_replicas(data_dir: str | Path, live_hostnames: set[str], *, keep: int = 4) -> int:
    """Remove replica homes that are not live container hostnames.

    Always keeps `keep` most recently modified dirs as a safety net.
    """
    root = Path(data_dir) / "replicas"
    if not root.is_dir():
        return 0
    dirs = [p for p in root.iterdir() if p.is_dir()]
    live = {h.strip() for h in live_hostnames if h and h.strip()}
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    kept_extra = 0
    for p in dirs:
        if p.name in live:
            continue
        if kept_extra < keep:
            kept_extra += 1
            continue
        shutil.rmtree(p, ignore_errors=True)
        removed += 1
    return removed


def live_hermes_hostnames() -> set[str]:
    import subprocess

    names: set[str] = set()
    try:
        out = subprocess.check_output(
            ["docker", "ps", "--filter", "name=hermes", "--format", "{{.ID}}\n{{.Names}}"],
            text=True,
            timeout=20,
        )
    except Exception:
        return names
    for line in out.splitlines():
        s = line.strip()
        if s:
            names.add(s)
            names.add(s[:12])
    return names


def main() -> int:
    data = os.environ.get("HERMES_DATA_DIR") or os.environ.get("ASSISTANT_DATA_DIR") or "/data/assistant"
    result = promote_shared_cron(data)
    prune = os.environ.get("HERMES_CRON_PRUNE_REPLICAS", "1").strip().lower() in {"1", "true", "yes", "on"}
    removed = 0
    if prune and result.get("action") in {"promoted", "keep_shared"}:
        removed = prune_stale_replicas(data, live_hermes_hostnames())
    print(
        f"HERMES_CRON_SHARE action={result.get('action')} "
        f"shared_jobs={result.get('shared_jobs')} "
        f"replica_files={result.get('replica_files')} "
        f"pruned={removed}"
    )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

