#!/usr/bin/env python3
"""Remove plaintext secret exports after deploy / restore / OpenBao seed.

SoT for API keys is OpenBao KV. Compose may briefly use ASSISTANT_DATA_DIR/.env.openbao
(env_file, required:false). After the stack is up, delete those host exports so a
host scan cannot list secrets. Re-run: bash run.sh load-openbao-env before the next
compose recreate when ENABLE_OPENBAO=1.

Also strips seeded API-key values from ROOT/.env (keys kept empty) so the stack
.env is flags/bootstrap only.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parents[2])
ENV_PATH = ROOT / ".env"
DATA_DIR = Path(
    os.environ.get("ASSISTANT_DATA_DIR")
    or os.environ.get("HERMES_DATA_DIR")
    or "/data/assistant"
)

# Keep OpenBao bootstrap + non-secret ops flags; wipe values for these after seed.
SCRUB_VALUE_KEYS = (
    "N9ROUTER_API_KEY",
    "N9ROUTER_INITIAL_PASSWORD",
    "OMNIROUTER_API_KEY",
    "OMNIROUTER_INITIAL_PASSWORD",
    "API_SERVER_KEY",
    "GATEWAY_API_KEYS",
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "HERMES_DASHBOARD_PASSWORD",
    "HERMES_DASHBOARD_SECRET",
    "MEMORY_DB_PASSWORD",
    "ZALO_API_TOKEN",
    "ZALO_PLUGIN_TOKEN",
    "GRAFANA_ADMIN_PASSWORD",
    "TELEGRAM_BOT_TOKEN",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "FAL_KEY",
    "FLUXAI_API_KEY",
    "POLLINATIONS_API_KEY",
)


def _scrub_env_file(path: Path) -> int:
    if not path.is_file():
        return 0
    lines_out: list[str] = []
    changed = 0
    want = {k.casefold() for k in SCRUB_VALUE_KEYS}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in line:
            lines_out.append(line)
            continue
        key, _, val = line.partition("=")
        k = key.strip()
        if k.casefold() in want and str(val).strip() and not str(val).strip().startswith("CHANGE_ME"):
            lines_out.append(f"{k}=")
            changed += 1
        else:
            lines_out.append(line)
    if changed:
        path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return changed


def _unlink(path: Path) -> bool:
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError as e:
        print(f"WARN: could not remove {path}: {e}", file=sys.stderr)
    return False


def main() -> int:
    removed = []
    for p in (
        DATA_DIR / ".env.openbao",
        DATA_DIR / ".env",
        DATA_DIR / "profile-options.env",
        ROOT / "profile-options.env",
    ):
        if _unlink(p):
            removed.append(str(p))
    n = _scrub_env_file(ENV_PATH)
    print(f"OK: removed {len(removed)} plaintext export(s); scrubbed {n} key value(s) in {ENV_PATH}")
    for p in removed:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
