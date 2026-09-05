#!/usr/bin/env python3
"""Static regression checks for update/watchdog exclusion and active flags."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    run = (ROOT / "run.sh").read_text(encoding="utf-8")
    watch = (ROOT / "scripts/main/stack-watch.sh").read_text(encoding="utf-8")
    workers = (ROOT / "architect/backup-restore/lib/workers.sh").read_text(encoding="utf-8")
    checks = {
        "update takes maintenance lock": 'flock 9' in run and 'stack-maintenance.lock' in run,
        "update repairs lock ownership": 'sudo chown "$(id -u):$(id -g)" "$maintenance_dir"' in run,
        "Omni repair is followed by secret scrub": "update-omnirouter failed" in run
        and run.find("do_scrub_plaintext_env", run.find("update-omnirouter failed")) > 0,
        "OpenBao secrets load before verified update backup": run.find("do_load_openbao_env_for_compose")
        < run.find('do_backup_first "update"'),
        "failed update backup scrubs transient secrets": 'if ! do_backup_first "update"; then\n    do_scrub_plaintext_env' in run,
        "routine update retains Docker rollback cache": 'UPDATE_AGGRESSIVE_PRUNE:-inactive' in run,
        "unrelated component update skips Zalo restart": 'skip Zalo plugin sync for unrelated component update' in run,
        "update avoids pre-compose Hermes restart": 'SYNC_ZALO_RESTART=0 bash "${SCRIPTS_DIR}/sync-zalo-plugins.sh"' in run,
        "selected component is actually recreated once": 'compose up -d --no-deps --build --force-recreate "$svc"' in run,
        "watchdog skips maintenance": 'flock -n 9' in watch and 'skip heal cycle' in watch,
        "notify uses canonical flag parser": 'if ! _env_active "${ENABLE_NOTIFY:-}"' in run,
        "security uses canonical flag parser": 'if ! _env_active "${ENABLE_SECURITY:-}"' in run,
        "retired router has no runtime profile": 'profile 9router' not in run and 'ENABLE_9ROUTER' not in workers,
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
