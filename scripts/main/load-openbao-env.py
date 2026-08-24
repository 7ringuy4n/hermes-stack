#!/usr/bin/env python3
"""Load OpenBao KV secret/assistant/api-keys into ASSISTANT_DATA_DIR/.env.openbao.

Compose can mount this via env_file when ENABLE_OPENBAO=1 so runtime secrets
are not .env-only. Re-run after OpenBao -dev restart (store is ephemeral).

  python3 scripts/main/load-openbao-env.py
  # or: bash run.sh first-setup-openbao  (seeds then exports)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parents[2])
ENV_PATH = ROOT / ".env"
DATA_DIR = Path(
    os.environ.get("ASSISTANT_DATA_DIR")
    or os.environ.get("HERMES_DATA_DIR")
    or "/data/assistant"
)
EXPORT_PATH = DATA_DIR / ".env.openbao"
BAO_ADDR = (os.environ.get("OPENBAO_ADDR") or "http://127.0.0.1:8200").rstrip("/")
SECRET_PATH = os.environ.get("OPENBAO_SECRET_PATH") or "secret/data/assistant/api-keys"


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        if k.strip():
            out[k.strip()] = v.strip().strip("'").strip('"')
    return out


def main() -> int:
    env = load_dotenv(ENV_PATH)
    token = (os.environ.get("OPENBAO_DEV_ROOT_TOKEN") or env.get("OPENBAO_DEV_ROOT_TOKEN") or "").strip()
    if not token or token.startswith("CHANGE_ME"):
        print("ERROR: OPENBAO_DEV_ROOT_TOKEN missing", file=sys.stderr)
        return 1
    req = urllib.request.Request(
        f"{BAO_ADDR}/v1/{SECRET_PATH.lstrip('/')}",
        headers={"X-Vault-Token": token},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            got = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as e:
        print(f"ERROR: OpenBao GET failed: {e}", file=sys.stderr)
        return 1
    data = ((got.get("data") or {}).get("data") or {})
    if not isinstance(data, dict) or not data:
        print(f"ERROR: empty KV at {SECRET_PATH} — run first-setup-openbao first", file=sys.stderr)
        return 1
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={v}" for k, v in sorted(data.items()) if str(v).strip()]
    EXPORT_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    try:
        os.chmod(EXPORT_PATH, 0o600)
    except OSError:
        pass
    print(f"OK: {len(lines)} keys → {EXPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
