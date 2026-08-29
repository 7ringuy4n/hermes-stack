#!/usr/bin/env python3
"""First-setup after the stack is up with 9Router enabled:

1) Login to 9Router with N9ROUTER_INITIAL_PASSWORD
2) Read Default Key from GET /api/keys
3) Write N9ROUTER_API_KEY into stack .env
4) Ensure combo `hermes` with OpenCode Free (`oc/*`) models
   (catalog from /api/providers/suggested-models — OpenCode is noAuth and
    does not appear on /v1/models until a combo exists)
5) Set combo strategy to round-robin (rotate)
6) Point Hermes at 9Router (custom) with default model `hermes`
7) Recreate embedding / dispatcher / hermes
8) Disk cleanup (prune build cache / dangling images / temp tarballs)

OpenCode Free (`oc/`) needs no upstream API key. Optional providers
(OpenRouter, DeepSeek, …) can still be added in the 9Router UI later.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(os.environ.get("STACK_ROOT", "/opt/assistant"))
HERMES_DATA = Path(os.environ.get("HERMES_DATA_DIR", "/data/assistant"))
PORT = int(os.environ.get("N9ROUTER_HOST_PORT", "20128"))
BASE = f"http://127.0.0.1:{PORT}"
COMBO_NAME = os.environ.get("N9ROUTER_DEFAULT_COMBO", "hermes")
DEFAULT_MODEL = os.environ.get("HERMES_DEFAULT_MODEL", COMBO_NAME)
# 9Router combo mode: round-robin rotates models each request (sticky limit 1 = rotate)
COMBO_STRATEGY = os.environ.get("N9ROUTER_COMBO_STRATEGY", "round-robin")
COMBO_STICKY_LIMIT = int(os.environ.get("N9ROUTER_COMBO_STICKY_LIMIT", "1"))


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


def http_json(opener, method: str, url: str, body: dict | None = None, timeout: int = 20):
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


def wait_9router(opener, password: str, tries: int = 60) -> None:
    print(f"==> wait for 9router {BASE}")
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
    raise SystemExit("9router not reachable")


def fetch_default_key(opener, password: str) -> str:
    wait_9router(opener, password)
    print("==> login 9router")
    status, body = http_json(opener, "POST", f"{BASE}/api/auth/login", {"password": password})
    if status != 200 or not body.get("success", True):
        raise SystemExit(f"login failed: {body}")

    print("==> GET /api/keys")
    _, data = http_json(opener, "GET", f"{BASE}/api/keys")
    keys = data.get("keys") or data.get("data") or []
    if not keys:
        print("==> no keys — try POST /api/keys")
        try:
            _, created = http_json(opener, "POST", f"{BASE}/api/keys", {"name": "Default Key"})
            keys = created.get("keys") or ([created] if created.get("key") else [])
            if not keys and created.get("key"):
                keys = [created]
        except Exception as e:
            raise SystemExit(
                f"no 9router API keys and create failed ({e}); create Default Key in dashboard"
            ) from e
    if not keys:
        raise SystemExit("no 9router API keys")

    def score(k: dict) -> tuple:
        name = (k.get("name") or "").lower()
        active = 1 if k.get("isActive", True) else 0
        default = 1 if "default" in name else 0
        return (active, default)

    keys = sorted(keys, key=score, reverse=True)
    key = keys[0].get("key") or keys[0].get("apiKey") or keys[0].get("token")
    if not key:
        raise SystemExit(f"key field missing: {keys[0]!r}")
    print(f"==> using key name={keys[0].get('name')!r} prefix={key[:12]}…")
    return key


def patch_hermes(key: str, model: str) -> None:
    cfg = HERMES_DATA / "config.yaml"
    if not cfg.exists():
        raise SystemExit(f"missing {cfg} — start hermes once first")
    text = cfg.read_text(encoding="utf-8")
    text = re.sub(r'(?m)^(  default:\s*).*$', rf'\1"{model}"', text, count=1)
    text = re.sub(r'(?m)^(  provider:\s*).*$', r'\1"custom"', text, count=1)
    text = re.sub(
        r'(?m)^(  base_url:\s*).*$',
        r'\1"http://9router:20128/v1"',
        text,
        count=1,
    )
    if re.search(r"(?m)^  api_key:\s*", text):
        text = re.sub(r'(?m)^(  api_key:\s*).*$', rf'\1"{key}"', text, count=1)
    else:
        text = re.sub(
            r'(?m)^(  base_url:\s*"http://9router:20128/v1"\s*)$',
            rf'\1\n  api_key: "{key}"',
            text,
            count=1,
        )

    provider_block = (
        "  9router:\n"
        '    base_url: "http://9router:20128/v1"\n'
        f'    api_key: "{key}"\n'
        "    api_mode: openai\n"
    )
    if re.search(r"(?m)^providers:\s*$", text):
        if re.search(r"(?m)^  9router:\s*$", text):
            text = re.sub(
                r"(?ms)^  9router:.*?(?=^\S|\Z)",
                provider_block,
                text,
                count=1,
            )
        else:
            text = re.sub(
                r"(?m)^providers:\s*$",
                "providers:\n" + provider_block.rstrip(),
                text,
                count=1,
            )
    else:
        text = text.rstrip() + "\n\nproviders:\n" + provider_block

    cfg.write_text(text, encoding="utf-8")

    envp = HERMES_DATA / ".env"
    lines: dict[str, str] = {}
    if envp.exists():
        for line in envp.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                lines[k.strip()] = v
    lines.update(
        {
            "OPENAI_API_KEY": key,
            "OPENAI_BASE_URL": "http://9router:20128/v1",
            "N9ROUTER_API_KEY": key,
            "OPENROUTER_API_KEY": key,
        }
    )
    envp.write_text("\n".join(f"{k}={v}" for k, v in lines.items()) + "\n", encoding="utf-8")
    envp.chmod(0o600)
    print(f"==> hermes model={model} provider=custom → 9router")


def recreate_services() -> None:
    """Recreate LLM-facing services using the same compose files as run.sh."""
    print("==> recreate embedding dispatcher hermes")
    env = load_env(ROOT / ".env")
    replicas = os.environ.get("HERMES_REPLICAS", "1")
    files = [
        f"--project-directory {ROOT}",
        f"-f {ROOT}/docker/docker-compose.yml",
    ]
    if env.get("ENABLE_MEDIA_FILE") == "1" or env.get("ENABLE_OCR") == "1" or env.get("ENABLE_JOBS") == "1" or env.get("ENABLE_SEARXNG") == "1":
        files.append(f"-f {ROOT}/docker/docker-compose.media.yml")
    if any(env.get(k) == "1" for k in ("ENABLE_SECURITY", "ENABLE_MONITOR", "ENABLE_NOTIFY", "ENABLE_OPENBAO", "ENABLE_SIEM", "ENABLE_AUTHZ", "ENABLE_CLOUDDRIVE")):
        files.append(f"-f {ROOT}/docker/docker-compose.security.yml")
    files_s = " ".join(files)
    # Drop leftover force-recreate aliases (hexprefix_assistant-hermes-N) that collide.
    subprocess.call(
        [
            "bash",
            "-lc",
            "docker ps -a --format '{{.Names}}' | awk '/^[0-9a-f]+_.*hermes/ {print}' | xargs -r docker rm -f",
        ]
    )
    cmd = (
        f"cd {ROOT} && set -a && . ./.env && set +a && "
        f"export COMPOSE_PROGRESS=plain && "
        f"docker compose {files_s} up -d --force-recreate "
        f"--scale hermes={replicas} embedding dispatcher hermes"
    )
    subprocess.check_call(["bash", "-lc", cmd])


OPENCODE_MODELS_URL = "https://opencode.ai/zen/v1/models"
# Fallback if suggested-models is unreachable (OpenCode Free catalog can change).
OPENCODE_FREE_FALLBACK = [
    "oc/big-pickle",
    "oc/deepseek-v4-flash-free",
    "oc/mimo-v2.5-free",
    "oc/hy3-free",
    "oc/nemotron-3-ultra-free",
    "oc/nemotron-3.5-lightning-free",
    "oc/laguna-s-2.1-free",
]


def list_oc_models(opener) -> list[str]:
    """OpenCode Free is noAuth — models are not listed on /v1/models until a combo
    exists. Fetch the free catalog via suggested-models and prefix with oc/."""
    q = urllib.parse.urlencode({"url": OPENCODE_MODELS_URL, "type": "opencode-free"})
    try:
        _, data = http_json(opener, "GET", f"{BASE}/api/providers/suggested-models?{q}")
        rows = data.get("data") or []
        oc = [
            f"oc/{m['id']}"
            for m in rows
            if isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"]
        ]
    except Exception as e:
        print(f"WARN suggested-models failed ({e}); using fallback list")
        oc = list(OPENCODE_FREE_FALLBACK)
    if not oc:
        print("WARN suggested-models empty; using fallback list")
        oc = list(OPENCODE_FREE_FALLBACK)
    # Prefer big-pickle first (stable OpenCode Free default)
    oc.sort(key=lambda x: (0 if x == "oc/big-pickle" else 1, x))
    return oc


def ensure_opencode_combo(opener, api_key: str) -> str:
    """Create/update combo with all current oc/* models. Returns combo name (model id)."""
    del api_key  # combo create uses session cookie; key kept for call-site symmetry
    oc = list_oc_models(opener)
    if not oc:
        raise SystemExit("no oc/* OpenCode Free models from 9Router")
    print(f"==> OpenCode Free models ({len(oc)}): {oc}")

    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == COMBO_NAME), None)

    if existing and existing.get("id"):
        cid = existing["id"]
        print(f"==> update combo {COMBO_NAME} ({cid})")
        status, body = http_json(
            opener,
            "PUT",
            f"{BASE}/api/combos/{cid}",
            {"name": COMBO_NAME, "models": oc},
        )
        if status not in (200, 201):
            raise SystemExit(f"combo update failed: {body}")
    else:
        print(f"==> create combo {COMBO_NAME}")
        status, body = http_json(
            opener,
            "POST",
            f"{BASE}/api/combos",
            {"name": COMBO_NAME, "models": oc},
        )
        if status not in (200, 201):
            raise SystemExit(f"combo create failed: {body}")

    # Combo is addressable as model id by name
    ensure_combo_round_robin(opener)
    return COMBO_NAME


def ensure_combo_round_robin(opener) -> None:
    """Set global + per-combo strategy to round-robin (rotate each request).

    9Router Combos UI stores per-combo mode as:
      comboStrategies.<name> = { "fallbackStrategy": "round-robin"|"fallback"|"fusion", ... }
    (field name is historical — it is the strategy, not only for fallback mode).
    A bare string is wrong: the UI spreads it into char keys and defaults the
    dropdown to Fallback.

    stickyLimit=1 means change model every request (true rotate). Higher values
    stick to the same member for N requests before advancing.
    """
    payload = {
        "comboStrategy": COMBO_STRATEGY,
        "comboStickyRoundRobinLimit": COMBO_STICKY_LIMIT,
        # Also clamp provider sticky so UI "round-robin" matches rotate behavior
        "stickyRoundRobinLimit": COMBO_STICKY_LIMIT,
        "comboStrategies": {
            COMBO_NAME: {"fallbackStrategy": COMBO_STRATEGY},
        },
    }
    print(
        f"==> combo strategy {COMBO_NAME}.fallbackStrategy={COMBO_STRATEGY} "
        f"(stickyLimit={COMBO_STICKY_LIMIT})"
    )
    status, body = http_json(opener, "PATCH", f"{BASE}/api/settings", payload)
    if status not in (200, 201):
        raise SystemExit(f"settings patch failed: {body}")
    # Verify shape the Combos UI actually reads
    _, settings = http_json(opener, "GET", f"{BASE}/api/settings")
    got = ((settings.get("comboStrategies") or {}).get(COMBO_NAME) or {})
    if isinstance(got, dict):
        mode = got.get("fallbackStrategy")
    else:
        mode = got
    if mode != COMBO_STRATEGY:
        raise SystemExit(
            f"combo strategy verify failed: expected {COMBO_STRATEGY!r}, got {got!r}"
        )


def cleanup_after_setup() -> None:
    """Free disk after a successful first-setup (build cache, dangling images, temps)."""
    print("==> cleanup disk after first-setup")
    cmds = [
        "docker builder prune -af",
        "docker image prune -af",
        "docker container prune -f",
        "rm -rf /tmp/assistant /tmp/assistant-low.tgz /tmp/9r-*.json 2>/dev/null || true",
        "df -h / | tail -1",
    ]
    for cmd in cmds:
        print("$", cmd)
        try:
            subprocess.check_call(["bash", "-lc", cmd])
        except subprocess.CalledProcessError as e:
            print(f"WARN cleanup step failed ({e.returncode}): {cmd}")


def verify(key: str, model: str) -> None:
    req = urllib.request.Request(
        f"{BASE}/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    ids = [m.get("id") for m in data.get("data") or []]
    print(f"==> 9router /v1/models ok ({len(ids)}): {ids[:12]}")
    if model not in ids:
        print(f"WARN combo model {model!r} not listed yet")
    print(f"    hermes default model id: {model}")
    # smoke one completion
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


def pin_image_backends(env: dict[str, str]) -> None:
    """Media|File worker: empty IMAGE_BACKENDS leaves Hermes inventing PIL/matplotlib. Pin dispatcher."""
    media_on = (env.get("ENABLE_MEDIA_FILE") or os.environ.get("ENABLE_MEDIA_FILE") or "0").strip()
    if media_on != "1":
        return
    cur = (env.get("IMAGE_BACKENDS") or "").strip()
    if cur:
        print(f"OK: IMAGE_BACKENDS already {cur}")
        return
    want = "comfy-cpu,comfy-gpu,omni"
    set_env_key(ROOT / ".env", "IMAGE_BACKENDS", want)
    env["IMAGE_BACKENDS"] = want
    print(f"OK: pinned IMAGE_BACKENDS={want}")


def main() -> int:
    env = load_env(ROOT / ".env")
    password = env.get("N9ROUTER_INITIAL_PASSWORD") or ""
    if not password:
        raise SystemExit("N9ROUTER_INITIAL_PASSWORD empty")

    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    key = fetch_default_key(opener, password)
    set_env_key(ROOT / ".env", "N9ROUTER_API_KEY", key)
    print(f"==> wrote N9ROUTER_API_KEY to {ROOT / '.env'}")

    model = ensure_opencode_combo(opener, key)
    set_env_key(ROOT / ".env", "HERMES_DEFAULT_MODEL", model)
    set_env_key(ROOT / ".env", "N9ROUTER_DEFAULT_COMBO", COMBO_NAME)
    set_env_key(ROOT / ".env", "N9ROUTER_COMBO_STRATEGY", COMBO_STRATEGY)
    pin_image_backends(env)

    for _ in range(30):
        if (HERMES_DATA / "config.yaml").exists():
            break
        time.sleep(2)
    else:
        raise SystemExit(f"missing {HERMES_DATA / 'config.yaml'}")

    # Allow env override after combo ensure
    model = os.environ.get("HERMES_DEFAULT_MODEL") or model
    patch_hermes(key, model)
    recreate_services()
    time.sleep(5)
    verify(key, model)
    cleanup_after_setup()
    print("OK: first-setup 9router → hermes complete (OpenCode round-robin)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read()[:300]!r}", file=sys.stderr)
        raise SystemExit(1) from e
