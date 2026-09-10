#!/usr/bin/env python3
"""Unit: exact retired defaults migrate; operator choices are preserved."""
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
            "ZALO_INBOUND_QUEUE_MAX=8\n"
            "CUSTOM_URL=https://operator.example\n",
            encoding="utf-8",
        )
        changed = mod.migrate_supported_values(env)
        text = env.read_text(encoding="utf-8")
        checks = {
            "known defaults migrated": set(changed)
            == {"ZALO_PLUGIN_URL", "ZALO_BRIDGE_URL", "ZALO_INBOUND_QUEUE_MAX"},
            "Traefik route written twice": text.count(mod.ZALO_TRAEFIK_URL) == 2,
            "retired queue cap migrated": "ZALO_INBOUND_QUEUE_MAX=16" in text,
            "custom route preserved": "CUSTOM_URL=https://operator.example" in text,
            "legacy values removed": not any(value in text for value in mod.LEGACY_ZALO_URLS),
        }
        custom = Path(tmp) / "custom.env"
        custom.write_text("ZALO_INBOUND_QUEUE_MAX=24\n", encoding="utf-8")
        custom_changed = mod.migrate_supported_values(custom)
        checks["custom queue cap preserved"] = (
            custom_changed == []
            and custom.read_text(encoding="utf-8") == "ZALO_INBOUND_QUEUE_MAX=24\n"
        )
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
