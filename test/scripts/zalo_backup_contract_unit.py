#!/usr/bin/env python3
"""Static contract for complete, restorable Zalo backup state."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP = (ROOT / "architect/backup-restore/lib/backup.sh").read_text(encoding="utf-8")


def main() -> int:
    checks = {
        "session credential is required": 'assistant_backup_fail "Zalo credentials are missing"' in BACKUP,
        "session credential is backed up": "zalo/session/credentials.json" in BACKUP,
        "identity allowlists are backed up": "zalo/identity/${file}" in BACKUP,
        "session credential is restored before service": (
            BACKUP.index('zalo/session/credentials.json')
            < BACKUP.index('systemctl --user enable --now com.hermes.zaloplugin.service')
        ),
        "credential permissions stay restrictive": 'chmod 600 "${ZALO_DATA_DIR:-${HOME}/.hermes-zalo}/credentials.json"' in BACKUP,
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
