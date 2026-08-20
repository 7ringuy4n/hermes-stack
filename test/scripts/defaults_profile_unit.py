# -*- coding: utf-8 -*-
"""Local unit: worker defaults (no VPS)."""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKERS = ROOT / "architect" / "backup-restore" / "lib" / "workers.sh"
CLASSIFY = ROOT / "architect" / "models" / "model-router" / "config" / "classify.json"
COMPOSE = ROOT / "docker" / "docker-compose.yml"
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _default(text: str, key: str) -> str | None:
    m = re.search(rf'export {re.escape(key)}="\$\{{{re.escape(key)}:-([^}}]+)\}}"', text)
    return m.group(1) if m else None


def main() -> int:
    text = WORKERS.read_text(encoding="utf-8")
    compose = COMPOSE.read_text(encoding="utf-8")
    classify = CLASSIFY.read_text(encoding="utf-8")
    fails = 0
    for banned in ("ASSISTANT_PROFILE", "low|medium|high"):
        if banned in text and "case \"$ASSISTANT_PROFILE\"" in text:
            print(f"FAIL workers.sh still maps {banned}")
            fails += 1
    if 'WORKER_SCHEDULE="${WORKER_SCHEDULE:-inactive}"' not in text:
        print("FAIL WORKER_SCHEDULE default missing")
        fails += 1
    else:
        print("PASS WORKER_SCHEDULE default inactive")
    checks = [
        ("ENABLE_OMNIROUTER", "1"),
        ("ENABLE_MODEL_ROUTER", "1"),
        ("ENABLE_OPENVPN", "0"),
        ("ENABLE_API_GATEWAY", "1"),
        ("ZALO_INBOUND_QUEUE", "1"),
        ("TRAEFIK_MODE", "local"),
        ("HERMES_REPLICAS", "1"),
    ]
    for key, want in checks:
        got = _default(text, key)
        if got != want:
            print(f"FAIL {key} default={got!r} want={want!r}")
            fails += 1
        else:
            print(f"PASS {key} default={want}")
    if "container_name: valkey" not in compose:
        print("FAIL valkey container name missing")
        fails += 1
    else:
        print("PASS valkey container name")
    if 'profiles: ["media"]' not in compose and "profiles: [\"media\"]" not in compose:
        print("FAIL dispatcher missing media compose profile")
        fails += 1
    else:
        print("PASS dispatcher media compose profile")
    if "profiles: [\"schedule\"]" not in compose:
        print("FAIL schedule-worker missing compose profile")
        fails += 1
    else:
        print("PASS schedule-worker compose profile")
    if "container_name: router-worker" not in compose:
        print("FAIL router-worker rename missing")
        fails += 1
    else:
        print("PASS router-worker container name")
    if '"max_tokens"' in classify:
        print("FAIL classify.json still has max_tokens")
        fails += 1
    else:
        print("PASS classify.json has no max_tokens")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
