#!/usr/bin/env python3
"""Move the OpenBao bootstrap token out of repository .env storage."""
from __future__ import annotations

import os
import secrets
from pathlib import Path


ROOT = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parents[2])
ENV_PATH = ROOT / ".env"
DATA_DIR = Path(os.environ.get("ASSISTANT_DATA_DIR") or "/data/assistant")
TOKEN_PATH = Path(
    os.environ.get("OPENBAO_TOKEN_FILE") or DATA_DIR / "openbao" / "root-token"
)


def migrate() -> bool:
    lines = ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines() if ENV_PATH.is_file() else []
    kept: list[str] = []
    token = (os.environ.get("OPENBAO_DEV_ROOT_TOKEN") or "").strip()
    removed = False
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and key.strip() == "OPENBAO_DEV_ROOT_TOKEN":
            candidate = value.strip().strip("'").strip('"')
            if candidate and not candidate.startswith("CHANGE_ME") and not token:
                token = candidate
            removed = True
            continue
        kept.append(line)
    if not token or token.startswith("CHANGE_ME"):
        token = secrets.token_urlsafe(48)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    os.chmod(TOKEN_PATH, 0o600)
    if removed:
        ENV_PATH.write_text("\n".join(kept) + "\n", encoding="utf-8")
        os.chmod(ENV_PATH, 0o600)
    return True


if __name__ == "__main__":
    ok = migrate()
    print("OK: OpenBao bootstrap token uses protected external file" if ok else "WARN: OpenBao bootstrap token is not initialized")
