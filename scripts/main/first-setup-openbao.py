#!/usr/bin/env python3
"""High first-setup: seed API keys from .env into OpenBao (+ export .env.openbao).

SoT after this script: OpenBao KV at secret/assistant/api-keys (UI on :8200).
Host .env stays for worker/component flags, paths, OpenBao bootstrap token, and Compose interpolate.

Usage (stack already up with the security/OpenBao components enabled):
  python3 scripts/main/first-setup-openbao.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parents[2])
ENV_PATH = ROOT / ".env"
DATA_DIR = Path(os.environ.get("ASSISTANT_DATA_DIR") or os.environ.get("HERMES_DATA_DIR") or "/data/assistant")
EXPORT_PATH = DATA_DIR / ".env.openbao"

BAO_ADDR = (os.environ.get("OPENBAO_ADDR") or "http://127.0.0.1:8200").rstrip("/")
BAO_TOKEN = os.environ.get("OPENBAO_DEV_ROOT_TOKEN") or ""
SECRET_PATH = os.environ.get("OPENBAO_SECRET_PATH") or "secret/data/assistant/api-keys"

# Keys copied from .env → OpenBao (empty values skipped)
SEED_KEYS = (
    "N9ROUTER_API_KEY",
    "N9ROUTER_INITIAL_PASSWORD",
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "HERMES_DASHBOARD_PASSWORD",
    "HERMES_DASHBOARD_SECRET",
    "MEMORY_DB_PASSWORD",
    "ZALO_API_TOKEN",
    "GRAFANA_ADMIN_PASSWORD",
    "ZALO_PLUGIN_TOKEN",
    "TELEGRAM_BOT_TOKEN",
)


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


def ensure_kv_v2(token: str) -> None:
    # Dev mode usually mounts secret/ as kv v2 already.
    try:
        http_json("GET", f"{BAO_ADDR}/v1/sys/mounts", token)
    except urllib.error.HTTPError as e:
        print(f"WARN: mounts check failed: {e}", flush=True)


def main() -> int:
    env = load_dotenv(ENV_PATH)
    token = BAO_TOKEN or env.get("OPENBAO_DEV_ROOT_TOKEN", "")
    if not token or token.startswith("CHANGE_ME"):
        print("ERROR: set OPENBAO_DEV_ROOT_TOKEN in .env (OpenBao root token)", file=sys.stderr)
        return 1

    wait_ready(token)
    ensure_kv_v2(token)

    payload: dict[str, str] = {}
    for key in SEED_KEYS:
        val = (os.environ.get(key) or env.get(key) or "").strip()
        if val and not val.startswith("CHANGE_ME"):
            payload[key] = val

    if not payload:
        print("WARN: no API keys found to seed (fill .env then re-run)", flush=True)
    else:
        body = {"data": payload}
        http_json("POST", f"{BAO_ADDR}/v1/{SECRET_PATH.lstrip('/')}", token, body)
        # Verify readable (OpenBao -dev is in-memory; empty UI usually means seed never stuck)
        try:
            got = http_json("GET", f"{BAO_ADDR}/v1/{SECRET_PATH.lstrip('/')}", token)
            data = ((got.get("data") or {}).get("data") or {})
            if not isinstance(data, dict) or not data:
                raise SystemExit(f"OpenBao verify empty after seed at {SECRET_PATH}")
            missing = [k for k in payload if k not in data]
            if missing:
                raise SystemExit(f"OpenBao verify missing keys: {missing}")
            print(
                f"OK: seeded {len(payload)} keys → {SECRET_PATH} "
                f"({', '.join(sorted(data.keys()))})",
                flush=True,
            )
        except urllib.error.HTTPError as e:
            raise SystemExit(f"OpenBao verify GET failed: {e}") from e

    # Export for backup / local consumers (SoT remains OpenBao UI)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={v}" for k, v in sorted(payload.items())]
    EXPORT_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    try:
        os.chmod(EXPORT_PATH, 0o600)
    except OSError:
        pass
    print(f"OK: wrote {EXPORT_PATH}", flush=True)
    port = os.environ.get("OPENBAO_PORT", "8200")
    print(
        f"UI:  http://127.0.0.1:{port}  → Secrets → secret/ → assistant/api-keys\n"
        f"     (token = OPENBAO_DEV_ROOT_TOKEN; -dev store is wiped on OpenBao restart "
        f"— re-run: bash run.sh first-setup-openbao)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
