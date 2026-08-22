#!/usr/bin/env bash
# Seed zalo_admin_users.txt from postgres zalo_entities when allowlist is missing/corrupt.
set -euo pipefail
ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
ADMIN_FILE="${ZALO_ADMIN_USERS_FILE:-${DATA_DIR}/zalo_admin_users.txt}"

python3 - <<'PY'
import os
import subprocess
import sys
from pathlib import Path

data_dir = Path(os.environ.get("HERMES_DATA_DIR") or os.environ.get("ASSISTANT_DATA_DIR") or "/data/assistant")
admin_file = Path(os.environ.get("ZALO_ADMIN_USERS_FILE") or data_dir / "zalo_admin_users.txt")


def psql_rows(sql: str) -> list[tuple[str, str]]:
    pg = subprocess.check_output(
        ["docker", "ps", "-q", "--filter", "name=^postgres$"], text=True
    ).strip().split()
    if not pg:
        return []
    env: dict[str, str] = {}
    for env_path in (Path("/opt/assistant/.env"), Path(os.environ.get("STACK_ROOT", "/opt/assistant")) / ".env"):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
        break
    user = env.get("MEMORY_DB_USER", "hermes")
    db = env.get("MEMORY_DB_NAME", "hermes_memory")
    cmd = ["docker", "exec", pg[0], "psql", "-U", user, "-d", db, "-t", "-A", "-c", sql]
    out = subprocess.check_output(cmd, text=True, errors="replace")
    rows: list[tuple[str, str]] = []
    for line in out.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= 2 and parts[0].strip():
            rows.append((parts[0].strip(), parts[1].strip()))
    return rows


def allowlist_ok(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size > 512:
        return False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        uid, _, name = raw.partition("|")
        if uid.strip().isdigit():
            return True
    return False


if allowlist_ok(admin_file):
    print("ADMIN_SEED_SKIP ok")
    sys.exit(0)

admins = psql_rows(
    "SELECT id, COALESCE(NULLIF(name,''),'Tn') FROM zalo_entities WHERE kind='admin' LIMIT 5"
)
if not admins:
    print("ADMIN_SEED_SKIP no postgres admins")
    sys.exit(0)

admin_file.parent.mkdir(parents=True, exist_ok=True)
admin_file.write_text(
    "\n".join(f"{uid}|{name}" for uid, name in admins) + "\n",
    encoding="utf-8",
)
print("ADMIN_SEED_OK", len(admins))
PY
