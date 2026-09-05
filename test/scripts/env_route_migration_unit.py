#!/usr/bin/env python3
"""Unit: exact legacy Zalo defaults migrate; custom routes are preserved."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts/main/cleanup-obsolete-env.py"
sys.path.insert(0, str(MODULE.parent))
spec = importlib.util.spec_from_file_location("cleanup_obsolete_env", MODULE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / ".env"
        env.write_text(
            "ZALO_PLUGIN_URL=http://zalo-proxy:8787\n"
            "ZALO_BRIDGE_URL=http://host.docker.internal:8787\n"
            "CUSTOM_URL=https://operator.example\n",
            encoding="utf-8",
        )
        changed = mod.migrate_supported_values(env)
        text = env.read_text(encoding="utf-8")
        checks = {
            "both known routes migrated": set(changed) == {"ZALO_PLUGIN_URL", "ZALO_BRIDGE_URL"},
            "Traefik route written twice": text.count(mod.ZALO_TRAEFIK_URL) == 2,
            "custom route preserved": "CUSTOM_URL=https://operator.example" in text,
            "legacy values removed": not any(value in text for value in mod.LEGACY_ZALO_URLS),
        }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
