#!/usr/bin/env python3
"""Import OpenBao KV export from backup into a running OpenBao -dev instance."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


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
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw) if raw.strip() else {}


def extract_kv_payload(doc: dict) -> dict[str, str]:
    if doc.get("note"):
        return {}
    data = doc.get("data") or {}
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        inner = data["data"]
    elif isinstance(doc.get("data"), dict):
        inner = doc["data"]
    else:
        inner = {}
    out: dict[str, str] = {}
    for k, v in inner.items():
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out[str(k)] = s
    return out


def load_backup_payload(path: Path) -> dict[str, str]:
    """Read a normal KV JSON export or a historical transient env export."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return {k: v for k, v in load_dotenv(path).items() if str(v).strip()}
    return extract_kv_payload(doc)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: restore_openbao_kv.py <kv-export.json>", file=sys.stderr)
        return 2
    kv_path = Path(sys.argv[1])
    if not kv_path.is_file():
        print(f"ERROR: missing {kv_path}", file=sys.stderr)
        return 1
    payload = load_backup_payload(kv_path)
    if not payload:
        print(f"ERROR: no recoverable KV keys in {kv_path}", file=sys.stderr)
        return 1

    root = Path(os.environ.get("ROOT") or "/opt/assistant")
    env = load_dotenv(root / ".env")
    token_file = Path(
        os.environ.get("OPENBAO_TOKEN_FILE")
        or os.environ.get("ASSISTANT_DATA_DIR", "/data/assistant") + "/openbao/root-token"
    )
    token = (os.environ.get("OPENBAO_DEV_ROOT_TOKEN") or env.get("OPENBAO_DEV_ROOT_TOKEN") or "").strip()
    if not token and token_file.is_file():
        token = token_file.read_text(encoding="utf-8", errors="replace").strip()
    if not token or token.startswith("CHANGE_ME"):
        print("ERROR: OpenBao bootstrap token missing", file=sys.stderr)
        return 1
    addr = (os.environ.get("OPENBAO_ADDR") or env.get("OPENBAO_ADDR") or "http://127.0.0.1:8200").rstrip("/")
    secret_path = os.environ.get("OPENBAO_SECRET_PATH") or env.get("OPENBAO_SECRET_PATH") or "secret/data/assistant/api-keys"
    path = secret_path.lstrip("/")
    if not path.startswith("secret/"):
        path = f"secret/data/{path.removeprefix('data/')}"

    try:
        http_json("POST", f"{addr}/v1/{path}", token, {"data": payload})
        got = http_json("GET", f"{addr}/v1/{path}", token)
        data = ((got.get("data") or {}).get("data") or {})
        if not isinstance(data, dict) or not data:
            print(f"ERROR: verify empty after import at {path}", file=sys.stderr)
            return 1
        print(f"OK: imported {len(payload)} OpenBao keys → {path}", flush=True)
        return 0
    except urllib.error.HTTPError as e:
        print(f"ERROR: OpenBao import failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
