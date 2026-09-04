#!/usr/bin/env python3
"""Load OpenBao KV secret/assistant/api-keys into ASSISTANT_DATA_DIR/.env.openbao.

Compose mounts this via env_file on hermes. Fills empty compose-required keys in
ROOT/.env from the same KV so docker compose can interpolate after env scrub.

  python3 scripts/main/load-openbao-env.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

from openbao_common import COMPOSE_HOST_KEYS, OBSOLETE_ENV_KEYS, OPENBAO_SECRET_PATH

ROOT = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parents[2])
ENV_PATH = ROOT / ".env"
DATA_DIR = Path(
    os.environ.get("ASSISTANT_DATA_DIR")
    or os.environ.get("HERMES_DATA_DIR")
    or "/data/assistant"
)
EXPORT_PATH = DATA_DIR / ".env.openbao"
BAO_ADDR = (os.environ.get("OPENBAO_ADDR") or "http://127.0.0.1:8200").rstrip("/")
SECRET_PATH = os.environ.get("OPENBAO_SECRET_PATH") or OPENBAO_SECRET_PATH


def repair_literal_newlines(path: Path) -> bool:
    """Fix host .env files whose newlines were written as literal \\n (unsourceable).

    Returns True when the file was rewritten. Never logs secret values.
    """
    if not path.is_file():
        return False
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    literal_n = text.count("\\n")
    real_n = text.count("\n")
    if literal_n <= max(real_n * 5, 20):
        return False
    fixed = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    fixed = fixed.replace("\r\n", "\n").replace("\r", "\n")
    if not fixed.endswith("\n"):
        fixed += "\n"
    bak = path.with_name(path.name + ".corrupt-literal-n.bak")
    try:
        if not bak.is_file():
            bak.write_bytes(raw)
    except OSError:
        pass
    path.write_text(fixed, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    print(
        f"OK: repaired literal \\\\n in {path} "
        f"(was {literal_n} escapes / {real_n} newlines → {fixed.count(chr(10))} lines)",
        flush=True,
    )
    return True


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    repair_literal_newlines(path)
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        if k.strip():
            out[k.strip()] = v.strip().strip("'").strip('"')
    return out


def upsert_env_keys(path: Path, updates: dict[str, str]) -> int:
    """Fill empty compose-required keys in ROOT/.env. Never overwrite non-empty values."""
    if not updates:
        return 0
    repair_literal_newlines(path)
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    have = {k.casefold() for k in updates}
    seen: set[str] = set()
    out: list[str] = []
    changed = 0
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key, _, val = line.partition("=")
        k = key.strip()
        kf = k.casefold()
        if kf not in have:
            out.append(line)
            continue
        seen.add(kf)
        cur = str(val).strip().strip("'").strip('"')
        want = updates[k] if k in updates else next(v for kk, v in updates.items() if kk.casefold() == kf)
        if cur and not cur.startswith("CHANGE_ME"):
            out.append(line)
            continue
        out.append(f"{k}={want}")
        changed += 1
    for k, v in updates.items():
        if k.casefold() in seen:
            continue
        out.append(f"{k}={v}")
        changed += 1
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return changed


def recover_root_token_from_container() -> str:
    """If host .env lost OPENBAO_DEV_ROOT_TOKEN, recover from the -dev container env."""
    import subprocess

    try:
        out = subprocess.check_output(
            [
                "docker",
                "inspect",
                "assistant-openbao-1",
                "--format",
                "{{range .Config.Env}}{{println .}}{{end}}",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except Exception:
        return ""
    for prefix in (
        "BAO_DEV_ROOT_TOKEN_ID=",
        "VAULT_DEV_ROOT_TOKEN_ID=",
        "BAO_DEV_ROOT_TOKEN=",
    ):
        for ln in out.splitlines():
            if ln.startswith(prefix):
                return ln.split("=", 1)[1].strip()
    return ""


def persist_root_token(token: str) -> None:
    if not token or not ENV_PATH.parent.is_dir():
        return
    repair_literal_newlines(ENV_PATH)
    lines: list[str] = []
    if ENV_PATH.is_file():
        lines = ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[str] = []
    seen = False
    for line in lines:
        if line.startswith("OPENBAO_DEV_ROOT_TOKEN="):
            out.append(f"OPENBAO_DEV_ROOT_TOKEN={token}")
            seen = True
        else:
            out.append(line)
    if not seen:
        out.append(f"OPENBAO_DEV_ROOT_TOKEN={token}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    try:
        os.chmod(ENV_PATH, 0o600)
    except OSError:
        pass


def _cleanup_obsolete_host_env() -> None:
    """Drop retired KEY= lines before refill (idempotent)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cleanup_obsolete_env",
        Path(__file__).resolve().parent / "cleanup-obsolete-env.py",
    )
    if not spec or not spec.loader:
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for p in (ENV_PATH, DATA_DIR / ".env"):
        gone = mod.remove_obsolete_keys(p, OBSOLETE_ENV_KEYS)
        if gone:
            print(
                f"OK: removed {len(gone)} obsolete key(s) from {p}: "
                f"{', '.join(sorted(set(gone)))}",
                flush=True,
            )


def main() -> int:
    try:
        _cleanup_obsolete_host_env()
    except Exception as e:  # noqa: BLE001
        print(f"WARN: obsolete env cleanup skipped: {e}", file=sys.stderr)
    env = load_dotenv(ENV_PATH)
    token = (os.environ.get("OPENBAO_DEV_ROOT_TOKEN") or env.get("OPENBAO_DEV_ROOT_TOKEN") or "").strip()
    if not token or token.startswith("CHANGE_ME"):
        recovered = recover_root_token_from_container()
        if recovered:
            persist_root_token(recovered)
            token = recovered
            print("OK: recovered OPENBAO_DEV_ROOT_TOKEN from openbao container", flush=True)
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
    skip = {k.casefold() for k in OBSOLETE_ENV_KEYS}
    lines = [
        f"{k}={v}"
        for k, v in sorted(data.items())
        if str(v).strip() and str(k).strip().casefold() not in skip
    ]
    EXPORT_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    try:
        os.chmod(EXPORT_PATH, 0o600)
    except OSError:
        pass
    fill = {
        k: str(data.get(k) or "").strip()
        for k in COMPOSE_HOST_KEYS
        if str(data.get(k) or "").strip()
    }
    n_fill = upsert_env_keys(ENV_PATH, fill)
    print(f"OK: {len(lines)} keys → {EXPORT_PATH}; filled {n_fill} compose host key(s) in {ENV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
