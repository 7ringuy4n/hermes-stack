#!/usr/bin/env python3
"""First-setup / update: seed API keys from .env into OpenBao KV.

SoT after seed: OpenBao at secret/assistant/api-keys (UI :8200).
The bootstrap token lives in a protected external token file. Compose-required
credentials are re-filled from KV by load-openbao-env before each up|update.

Usage:
  python3 scripts/main/first-setup-openbao.py          # core: seed missing + merge updates
  python3 scripts/main/first-setup-openbao.py --update  # same (explicit repair)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from openbao_common import (
    OBSOLETE_SECRET_KEYS,
    OPENBAO_SECRET_PATH,
    SEED_KEYS,
    is_secret_env_name,
)

ROOT = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parents[2])
ENV_PATH = ROOT / ".env"
DATA_DIR = Path(os.environ.get("ASSISTANT_DATA_DIR") or os.environ.get("HERMES_DATA_DIR") or "/data/assistant")
EXPORT_PATH = DATA_DIR / ".env.openbao"

BAO_ADDR = (os.environ.get("OPENBAO_ADDR") or "http://127.0.0.1:8200").rstrip("/")
BAO_TOKEN = os.environ.get("OPENBAO_DEV_ROOT_TOKEN") or ""
SECRET_PATH = os.environ.get("OPENBAO_SECRET_PATH") or OPENBAO_SECRET_PATH


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        if k:
            out[k] = v
    return out


def http_json(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-Vault-Token": token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw) if raw.strip() else {}


def wait_ready(token: str, tries: int = 30) -> None:
    url = f"{BAO_ADDR}/v1/sys/health"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status in (200, 429, 472, 473):
                    return
        except Exception:
            pass
        time.sleep(2)
        print(f"waiting for OpenBao ({i + 1}/{tries})…", flush=True)
    raise SystemExit(f"OpenBao not ready at {BAO_ADDR}")


def kv_get(token: str) -> dict[str, str]:
    try:
        got = http_json("GET", f"{BAO_ADDR}/v1/{SECRET_PATH.lstrip('/')}", token)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise
    data = ((got.get("data") or {}).get("data") or {})
    if not isinstance(data, dict):
        return {}
    return {k: str(v) for k, v in data.items() if str(v).strip()}


def kv_put(token: str, data: dict[str, str]) -> None:
    http_json("POST", f"{BAO_ADDR}/v1/{SECRET_PATH.lstrip('/')}", token, {"data": data})


def purge_obsolete(token: str, current: dict[str, str]) -> dict[str, str]:
    data = dict(current)
    removed = [k for k in OBSOLETE_SECRET_KEYS if k in data]
    if not removed:
        return data
    for k in removed:
        data.pop(k, None)
    kv_put(token, data)
    print(f"OK: purged obsolete OpenBao keys: {', '.join(removed)}")
    return data


def collect_seed_payload(env: dict[str, str]) -> dict[str, str]:
    payload: dict[str, str] = {}
    dynamic_keys = {key for key in env if is_secret_env_name(key)}
    dynamic_keys.update(key for key in os.environ if is_secret_env_name(key))
    for key in sorted(set(SEED_KEYS) | dynamic_keys):
        val = (os.environ.get(key) or env.get(key) or "").strip()
        if val and not val.startswith("CHANGE_ME"):
            payload[key] = val
    return payload


def export_openbao_file(data: dict[str, str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={v}" for k, v in sorted(data.items()) if str(v).strip()]
    EXPORT_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    try:
        os.chmod(EXPORT_PATH, 0o600)
    except OSError:
        pass
    print(f"OK: wrote {EXPORT_PATH}", flush=True)


def run_seed(*, update: bool = False) -> int:
    del update  # merge is always on — flag kept for CLI symmetry with other first-setup scripts
    env = load_dotenv(ENV_PATH)
    token_path = Path(
        os.environ.get("OPENBAO_TOKEN_FILE") or DATA_DIR / "openbao" / "root-token"
    )
    token = BAO_TOKEN or env.get("OPENBAO_DEV_ROOT_TOKEN", "")
    if not token and token_path.is_file():
        token = token_path.read_text(encoding="utf-8", errors="replace").strip()
    if not token or token.startswith("CHANGE_ME"):
        print("ERROR: initialize the protected OpenBao bootstrap token file", file=sys.stderr)
        return 1

    wait_ready(token)
    incoming = collect_seed_payload(env)
    existing = kv_get(token)
    merged = dict(existing)
    merged.update(incoming)
    merged = purge_obsolete(token, merged)

    if not merged and not incoming:
        print("WARN: no API keys in .env to seed — fill .env then re-run", flush=True)
    elif incoming:
        kv_put(token, merged)
        print(
            f"OK: seeded/merged {len(incoming)} key(s) → {SECRET_PATH} "
            f"(KV total {len(merged)})",
            flush=True,
        )
    elif merged:
        print(f"OK: KV unchanged ({len(merged)} keys); obsolete purge applied if any", flush=True)

    # Verify readable
    verify = kv_get(token)
    if incoming and not verify:
        raise SystemExit(f"OpenBao verify empty after seed at {SECRET_PATH}")

    export_openbao_file(verify or merged)
    port = os.environ.get("OPENBAO_PORT", "8200")
    print(
        f"UI:  http://127.0.0.1:{port}  → Secrets → secret/ → assistant/api-keys\n"
        f"     Token access (root-only): sudo cat {token_path}\n"
        f"     (-dev store is wiped on OpenBao restart "
        f"— re-run: bash run.sh first-setup-openbao)",
        flush=True,
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="Repair/sync KV from .env (merge)")
    args = ap.parse_args()
    return run_seed(update=args.update)


if __name__ == "__main__":
    raise SystemExit(main())
