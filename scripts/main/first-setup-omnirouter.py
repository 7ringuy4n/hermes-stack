#!/usr/bin/env python3
"""First-setup OmniRouter (OmniRoute) after ENABLE_OMNIROUTER=1:

1) Login with OMNIROUTER_INITIAL_PASSWORD (else N9ROUTER_INITIAL_PASSWORD)
2) Read/create Default Key → OMNIROUTER_API_KEY
3) Create/update combo `hermes` from all OpenCode Free `oc/*` models
4) Set combo strategy to round-robin
5) Recreate model-router so it picks up the key

OpenCode Free (`oc/`) needs no upstream API key.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(os.environ.get("STACK_ROOT", "/opt/assistant"))
PORT = int(os.environ.get("OMNIROUTER_HOST_PORT", "20129"))
BASE = f"http://127.0.0.1:{PORT}"
COMBO_NAME = os.environ.get("OMNIROUTER_DEFAULT_COMBO", "hermes")
COMBO_STRATEGY = os.environ.get("OMNIROUTER_COMBO_STRATEGY", "round-robin")
COMBO_STICKY_LIMIT = int(os.environ.get("OMNIROUTER_COMBO_STICKY_LIMIT", "1"))

OPENCODE_FREE_FALLBACK = [
    "oc/big-pickle",
    "oc/deepseek-v4-flash-free",
    "oc/mimo-v2.5-free",
    "oc/hy3-free",
    "oc/nemotron-3-ultra-free",
    "oc/north-mini-code-free",
]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        raise SystemExit(f"missing {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def set_env_key(path: Path, key: str, value: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    line = f"{key}={value}"
    if re.search(rf"(?m)^{re.escape(key)}=", text):
        text = re.sub(rf"(?m)^{re.escape(key)}=.*$", line, text)
    else:
        text = text.rstrip() + "\n" + line + "\n"
    path.write_text(text, encoding="utf-8")


def http_json(opener, method: str, url: str, body: dict | None = None, timeout: int = 25):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read()
        return resp.status, json.loads(raw.decode() or "{}") if raw else {}


def wait_login(opener, password: str, tries: int = 60) -> None:
    print(f"==> wait for omni-router {BASE}")
    for _ in range(tries):
        try:
            status, _ = http_json(opener, "POST", f"{BASE}/api/auth/login", {"password": password})
            if status == 200:
                return
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 200):
                return
        except Exception:
            pass
        time.sleep(2)
    raise SystemExit("omni-router not reachable")


def _looks_full_key(key: str) -> bool:
    k = (key or "").strip()
    return len(k) >= 20 and "*" not in k and k.startswith("sk-")


def fetch_default_key(opener, password: str, existing: str = "") -> str:
    wait_login(opener, password)
    print("==> login omni-router")
    status, body = http_json(opener, "POST", f"{BASE}/api/auth/login", {"password": password})
    if status != 200 or not body.get("success", True):
        raise SystemExit(f"login failed: {body}")

    if _looks_full_key(existing):
        print("==> keep existing OMNIROUTER_API_KEY")
        return existing.strip()

    # GET /api/keys returns a masked token after create — mint a fresh key once.
    print("==> POST /api/keys assistant-stack (full token only on create)")
    _, created = http_json(opener, "POST", f"{BASE}/api/keys", {"name": "assistant-stack"})
    key = (created.get("key") or created.get("apiKey") or created.get("token") or "").strip()
    if not _looks_full_key(key):
        raise SystemExit("omni-router create key did not return a full token")
    print(f"==> using key name=assistant-stack prefix={key[:12]}…")
    return key


def list_oc_models(opener) -> list[str]:
    """OpenCode Free models already published on OmniRoute /v1/models as oc/*."""
    try:
        _, data = http_json(opener, "GET", f"{BASE}/v1/models")
        ids = [
            m.get("id")
            for m in (data.get("data") or [])
            if isinstance(m, dict) and isinstance(m.get("id"), str)
        ]
        oc = [i for i in ids if i.startswith("oc/")]
    except Exception as e:
        print(f"WARN /v1/models failed ({e}); using fallback list")
        oc = list(OPENCODE_FREE_FALLBACK)
    if not oc:
        print("WARN no oc/* on /v1/models; using fallback list")
        oc = list(OPENCODE_FREE_FALLBACK)
    oc = list(dict.fromkeys(oc))
    oc.sort(key=lambda x: (0 if x == "oc/big-pickle" else 1, x))
    return oc


def drop_probe_combos(opener) -> None:
    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    for c in data.get("combos") or []:
        name = (c.get("name") or "").strip()
        cid = c.get("id")
        if name.startswith("probe-") and cid:
            print(f"==> delete leftover combo {name}")
            try:
                http_json(opener, "DELETE", f"{BASE}/api/combos/{cid}")
            except Exception as e:
                print(f"WARN delete {name}: {e}")


def ensure_opencode_combo(opener) -> str:
    oc = list_oc_models(opener)
    if not oc:
        raise SystemExit("no oc/* OpenCode Free models from omni-router")
    print(f"==> OpenCode Free models ({len(oc)}): {oc}")
    drop_probe_combos(opener)

    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == COMBO_NAME), None)
    payload = {
        "name": COMBO_NAME,
        "models": oc,
        "strategy": COMBO_STRATEGY,
        "description": "OpenCode Free (oc/*) round-robin",
    }

    if existing and existing.get("id"):
        cid = existing["id"]
        print(f"==> update combo {COMBO_NAME} ({cid})")
        status, body = http_json(opener, "PUT", f"{BASE}/api/combos/{cid}", payload)
        if status not in (200, 201):
            raise SystemExit(f"combo update failed: {body}")
    else:
        print(f"==> create combo {COMBO_NAME}")
        status, body = http_json(opener, "POST", f"{BASE}/api/combos", payload)
        if status not in (200, 201):
            raise SystemExit(f"combo create failed: {body}")

    ensure_combo_round_robin(opener)
    return COMBO_NAME


def ensure_combo_round_robin(opener) -> None:
    payload = {
        "comboStrategy": COMBO_STRATEGY,
        "comboStickyRoundRobinLimit": COMBO_STICKY_LIMIT,
        "stickyRoundRobinLimit": COMBO_STICKY_LIMIT,
    }
    print(f"==> settings comboStrategy={COMBO_STRATEGY} stickyLimit={COMBO_STICKY_LIMIT}")
    status, body = http_json(opener, "PATCH", f"{BASE}/api/settings", payload)
    if status not in (200, 201):
        print(f"WARN settings patch failed: {body}")
        return
    _, settings = http_json(opener, "GET", f"{BASE}/api/settings")
    got = settings.get("comboStrategy")
    if got != COMBO_STRATEGY:
        print(f"WARN comboStrategy verify: expected {COMBO_STRATEGY!r}, got {got!r}")


def recreate_model_router() -> None:
    print("==> recreate model-router")
    cmd = (
        f"cd {ROOT} && set -a && . ./.env && set +a && "
        f"export COMPOSE_PROGRESS=plain && "
        f"docker compose --project-directory {ROOT} -f {ROOT}/docker/docker-compose.yml "
        f"up -d --no-deps --force-recreate model-router"
    )
    subprocess.check_call(["bash", "-lc", cmd])


def verify(key: str, model: str) -> None:
    req = urllib.request.Request(
        f"{BASE}/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"WARN omni-router /v1/models HTTP {e.code}: {e.read()[:200]!r}")
        return
    ids = [m.get("id") for m in data.get("data") or []]
    print(f"==> omni-router /v1/models ok ({len(ids)})")
    if model not in ids:
        print(f"WARN combo model {model!r} not listed yet")
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
        }
    ).encode()
    req = urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            print(f"==> smoke chat {model} HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"WARN smoke chat {model} HTTP {e.code}: {e.read()[:200]!r}")


def main() -> int:
    env = load_env(ROOT / ".env")
    if env.get("ENABLE_OMNIROUTER", "0") not in {"1", "true", "yes", "on"}:
        print("SKIP: ENABLE_OMNIROUTER is not 1")
        return 0
    password = env.get("OMNIROUTER_INITIAL_PASSWORD") or env.get("N9ROUTER_INITIAL_PASSWORD") or ""
    if not password:
        raise SystemExit("OMNIROUTER_INITIAL_PASSWORD / N9ROUTER_INITIAL_PASSWORD empty")

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    key = fetch_default_key(opener, password, env.get("OMNIROUTER_API_KEY", ""))
    set_env_key(ROOT / ".env", "OMNIROUTER_API_KEY", key)
    print(f"==> wrote OMNIROUTER_API_KEY to {ROOT / '.env'}")

    model = ensure_opencode_combo(opener)
    set_env_key(ROOT / ".env", "OMNIROUTER_DEFAULT_COMBO", COMBO_NAME)
    set_env_key(ROOT / ".env", "OMNIROUTER_COMBO_STRATEGY", COMBO_STRATEGY)

    recreate_model_router()
    time.sleep(3)
    verify(key, model)
    print("OK: first-setup omni-router complete (OpenCode Free combo, round-robin)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read()[:300]!r}", file=sys.stderr)
        raise SystemExit(1) from e
