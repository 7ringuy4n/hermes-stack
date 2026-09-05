#!/usr/bin/env python3
"""Remove retired KEY= lines from host .env files (ROOT + ASSISTANT_DATA_DIR).

Does not log secret values. Safe to re-run. Called from scrub-plaintext-env and
load-openbao-env so update/up do not leave obsolete pins (e.g. ADMIN_API_TOKEN,
WEB_BACKENDS) that no longer match the combo-based core setup.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from openbao_common import OBSOLETE_ENV_KEYS

ZALO_TRAEFIK_URL = "http://traefik:8081/zalo-bridge"
LEGACY_ZALO_URLS = {
    "http://host.docker.internal:8787",
    "http://zalo-proxy:8787",
}

ROOT = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parents[2])
ENV_PATH = ROOT / ".env"
DATA_DIR = Path(
    os.environ.get("ASSISTANT_DATA_DIR")
    or os.environ.get("HERMES_DATA_DIR")
    or "/data/assistant"
)


def remove_obsolete_keys(path: Path, keys: tuple[str, ...] | list[str]) -> list[str]:
    if not path.is_file() or not keys:
        return []
    want = {k.casefold() for k in keys}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    kept: list[str] = []
    removed: list[str] = []
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in line:
            kept.append(line)
            continue
        key = line.partition("=")[0].strip()
        if key.casefold() in want:
            removed.append(key)
            continue
        kept.append(line)
    if not removed:
        return []
    path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return removed


def migrate_supported_values(path: Path) -> list[str]:
    """Migrate only exact retired stack defaults; preserve operator URLs."""
    if not path.is_file():
        return []
    changed: list[str] = []
    output: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, sep, value = line.partition("=")
        name = key.strip()
        current = value.strip().strip('"').strip("'") if sep else ""
        if name in {"ZALO_PLUGIN_URL", "ZALO_BRIDGE_URL"} and current in LEGACY_ZALO_URLS:
            output.append(f"{name}={ZALO_TRAEFIK_URL}")
            changed.append(name)
        else:
            output.append(line)
    if changed:
        path.write_text("\n".join(output) + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return changed


def main() -> int:
    paths = [ENV_PATH, DATA_DIR / ".env"]
    total = 0
    for p in paths:
        gone = remove_obsolete_keys(p, OBSOLETE_ENV_KEYS)
        if gone:
            total += len(gone)
            print(f"OK: removed {len(gone)} obsolete key(s) from {p}: {', '.join(sorted(set(gone)))}")
        migrated = migrate_supported_values(p)
        if migrated:
            total += len(migrated)
            print(f"OK: migrated {len(migrated)} Zalo route setting(s) in {p}: {', '.join(sorted(set(migrated)))}")
    if total == 0:
        print("OK: no obsolete env keys to remove")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
