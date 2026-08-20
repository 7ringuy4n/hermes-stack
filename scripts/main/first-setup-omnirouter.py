#!/usr/bin/env python3
"""First-setup OmniRouter (OmniRoute) after ENABLE_OMNIROUTER=1:

1) Login with OMNIROUTER_INITIAL_PASSWORD (else N9ROUTER_INITIAL_PASSWORD)
2) Read/create Default Key → OMNIROUTER_API_KEY
3) Ensure chat combo alias exists (OMNIROUTER_DEFAULT_COMBO, default ``hermes``)
   — do NOT hardcode chat member models; OmniRouter / UI choose models
4) Ensure classify combo ``classifier`` with all OpenCode Free (``oc/*``) models
5) Set combo strategy preference (round-robin)
6) Point Hermes at model-router; recreate router-worker for the key

Stack code sends combo *names* as OpenAI ``model``. Chat uses ``hermes``;
classify uses ``classifier`` (OpenCode members refreshed by this script).
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
PORT = int(os.environ.get("OMNIROUTER_HOST_PORT", "20129"))
BASE = f"http://127.0.0.1:{PORT}"
COMBO_NAME = os.environ.get("OMNIROUTER_DEFAULT_COMBO", "hermes")
CLASSIFY_COMBO_NAME = os.environ.get("OMNIROUTER_CLASSIFY_COMBO", "classifier")
COMBO_STRATEGY = os.environ.get("OMNIROUTER_COMBO_STRATEGY", "round-robin")
COMBO_STICKY_LIMIT = int(os.environ.get("OMNIROUTER_COMBO_STICKY_LIMIT", "1"))

OPENCODE_MODELS_URL = "https://opencode.ai/zen/v1/models"
OPENCODE_FREE_FALLBACK = [
    "oc/big-pickle",
    "oc/deepseek-v4-flash-free",
    "oc/mimo-v2.5-free",
    "oc/hy3-free",
    "oc/nemotron-3-ultra-free",
    "oc/nemotron-3.5-lightning-free",
    "oc/laguna-s-2.1-free",
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


def _combo_member_count(combo: dict) -> int:
    models = combo.get("models") or combo.get("members") or []
    return len(models) if isinstance(models, list) else 0


def ensure_opencode_provider(opener) -> None:
    """Ensure an OpenCode Free connection exists so ``oc/*`` models can route."""
    try:
        _, data = http_json(opener, "GET", f"{BASE}/api/providers")
    except Exception as e:
        print(f"WARN providers list failed: {e}")
        return
    conns = data.get("connections") or []
    for c in conns:
        if str(c.get("provider") or "").lower() == "opencode":
            print(f"==> keep OpenCode provider connection id={c.get('id')}")
            return
    print("==> create OpenCode Free provider connection")
    for payload in (
        {"provider": "opencode", "authType": "apikey", "name": "opencode-free", "isActive": True},
        {"provider": "opencode", "name": "opencode-free", "isActive": True},
    ):
        try:
            status, body = http_json(opener, "POST", f"{BASE}/api/providers", payload)
        except urllib.error.HTTPError as e:
            print(f"WARN create opencode provider HTTP {e.code}: {e.read()[:200]!r}")
            continue
        if status in (200, 201):
            print(f"==> OpenCode provider created: {body}")
            return
        print(f"WARN create opencode provider rejected: {body}")


def list_oc_models(opener) -> list[str]:
    """All OpenCode Free model ids (``oc/...``). Catalog is not always on /v1/models."""
    oc: list[str] = []

    # 1) Omni/9Router suggested-models helper (when present)
    q = urllib.parse.urlencode({"url": OPENCODE_MODELS_URL, "type": "opencode-free"})
    try:
        _, data = http_json(opener, "GET", f"{BASE}/api/providers/suggested-models?{q}")
        rows = data.get("data") or []
        oc = [
            f"oc/{m['id']}" if not str(m["id"]).startswith("oc/") else str(m["id"])
            for m in rows
            if isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"]
        ]
    except Exception as e:
        print(f"WARN suggested-models unavailable ({e})")

    # 2) Direct OpenCode Zen catalog
    if not oc:
        try:
            req = urllib.request.Request(
                OPENCODE_MODELS_URL,
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode() or "{}")
            rows = data.get("data") or data.get("models") or []
            for m in rows:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id") or m.get("name")
                if not isinstance(mid, str) or not mid.strip():
                    continue
                mid = mid.strip()
                oc.append(mid if mid.startswith("oc/") else f"oc/{mid}")
        except Exception as e:
            print(f"WARN OpenCode zen catalog failed ({e})")

    # 3) Already-published oc/* on /v1/models
    if not oc:
        try:
            _, data = http_json(opener, "GET", f"{BASE}/v1/models")
            for m in data.get("data") or []:
                mid = (m or {}).get("id") if isinstance(m, dict) else None
                if isinstance(mid, str) and mid.startswith("oc/"):
                    oc.append(mid)
        except Exception as e:
            print(f"WARN /v1/models oc scan failed ({e})")

    if not oc:
        print("WARN OpenCode catalog empty; using fallback list")
        oc = list(OPENCODE_FREE_FALLBACK)

    # Dedupe preserve order; prefer big-pickle first
    seen: set[str] = set()
    uniq: list[str] = []
    for mid in oc:
        if mid in seen:
            continue
        seen.add(mid)
        uniq.append(mid)
    uniq.sort(key=lambda x: (0 if x == "oc/big-pickle" else 1, x))
    return uniq


def ensure_classifier_combo(opener) -> str:
    """Create/update combo ``classifier`` with all current OpenCode Free models."""
    ensure_opencode_provider(opener)
    oc = list_oc_models(opener)
    if not oc:
        raise SystemExit("no oc/* OpenCode Free models for classifier combo")
    print(f"==> classifier OpenCode models ({len(oc)}): {oc}")

    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == CLASSIFY_COMBO_NAME), None)
    payload = {
        "name": CLASSIFY_COMBO_NAME,
        "models": oc,
        "strategy": COMBO_STRATEGY,
        "description": "Classify/intent combo — all OpenCode Free (oc/*) models",
    }
    if existing and existing.get("id"):
        cid = existing["id"]
        print(f"==> update combo {CLASSIFY_COMBO_NAME} ({cid}) members={len(oc)}")
        status, body = http_json(opener, "PUT", f"{BASE}/api/combos/{cid}", payload)
        if status not in (200, 201):
            raise SystemExit(f"classifier combo update failed: {body}")
    else:
        print(f"==> create combo {CLASSIFY_COMBO_NAME} members={len(oc)}")
        status, body = http_json(opener, "POST", f"{BASE}/api/combos", payload)
        if status not in (200, 201):
            raise SystemExit(f"classifier combo create failed: {body}")

    # Per-combo strategy (Omni/9Router Combos UI shape)
    try:
        http_json(
            opener,
            "PATCH",
            f"{BASE}/api/settings",
            {
                "comboStrategies": {
                    CLASSIFY_COMBO_NAME: {"fallbackStrategy": COMBO_STRATEGY},
                },
            },
        )
    except Exception as e:
        print(f"WARN classifier comboStrategies patch: {e}")
    return CLASSIFY_COMBO_NAME


def ensure_combo_alias(opener) -> str:
    """Ensure combo *name* exists. Never overwrite member models — Omni chooses."""
    drop_probe_combos(opener)

    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == COMBO_NAME), None)

    if existing and existing.get("id"):
        cid = existing["id"]
        n = _combo_member_count(existing)
        # Strategy/description only — omit "models" so Omni keeps operator membership.
        payload = {
            "name": COMBO_NAME,
            "strategy": COMBO_STRATEGY,
            "description": "Stack combo alias — member models managed in OmniRouter UI",
        }
        print(f"==> keep combo {COMBO_NAME} ({cid}) members={n} (not overwriting models)")
        status, body = http_json(opener, "PUT", f"{BASE}/api/combos/{cid}", payload)
        if status not in (200, 201):
            print(f"WARN combo metadata update failed: {body}")
        ensure_combo_round_robin(opener)
        if n == 0:
            print(
                f"WARN combo {COMBO_NAME!r} has no members — add models in OmniRouter Combos UI"
            )
        return COMBO_NAME

    # Create alias shell only. Prefer empty members; Omni/UI fills models.
    print(f"==> create combo alias {COMBO_NAME} (no hardcoded members)")
    for payload in (
        {
            "name": COMBO_NAME,
            "models": [],
            "strategy": COMBO_STRATEGY,
            "description": "Stack combo alias — member models managed in OmniRouter UI",
        },
        {
            "name": COMBO_NAME,
            "strategy": COMBO_STRATEGY,
            "description": "Stack combo alias — member models managed in OmniRouter UI",
        },
    ):
        try:
            status, body = http_json(opener, "POST", f"{BASE}/api/combos", payload)
        except urllib.error.HTTPError as e:
            print(f"WARN create attempt failed HTTP {e.code}: {e.read()[:200]!r}")
            continue
        if status in (200, 201):
            ensure_combo_round_robin(opener)
            print(
                f"NOTE: add member models for combo {COMBO_NAME!r} in OmniRouter Combos UI "
                "(do not hardcode in stack)"
            )
            return COMBO_NAME
        print(f"WARN create attempt rejected: {body}")

    raise SystemExit(
        f"could not create combo alias {COMBO_NAME!r} — create it in OmniRouter UI"
    )


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


def patch_hermes_model_router(key: str, model: str) -> None:
    print("==> patch Hermes config → model-router")
    env = os.environ.copy()
    env.setdefault("STACK_ROOT", str(ROOT))
    env.setdefault("HERMES_DATA_DIR", os.environ.get("HERMES_DATA_DIR", "/data/assistant"))
    rc = subprocess.call(
        [sys.executable, str(ROOT / "scripts" / "main" / "patch-hermes-model-router.py")],
        env=env,
    )
    if rc != 0:
        print("WARN: patch-hermes-model-router failed")


def recreate_model_router() -> None:
    print("==> recreate router-worker (model-router)")
    for name in ("router-worker", "model-router", "assistant-router-worker-1"):
        rc = subprocess.call(
            ["docker", "restart", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if rc == 0:
            print(f"==> restarted {name}")
            return
    print("WARN: could not restart router-worker by name — skip recreate")


def enable_omni_memory(opener: urllib.request.OpenerDirector) -> None:
    """Best-effort: enable OmniRoute conversational memory when API supports it."""
    for path, payload in (
        ("/api/v1/settings/memory", {"enabled": True}),
        ("/api/settings/memory", {"enabled": True}),
        ("/api/v1/memory", {"enabled": True}),
    ):
        try:
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{BASE}{path}",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with opener.open(req, timeout=10) as resp:
                if 200 <= resp.status < 300:
                    print(f"==> omni memory enabled via {path}")
                    return
        except Exception:
            continue
    print("NOTE: omni memory API not found — using OMNIROUTER_ENABLE_MEMORY container env")


def verify(key: str, combo: str) -> None:
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
    if combo not in ids:
        print(f"WARN combo alias {combo!r} not listed on /v1/models yet")
    body = json.dumps(
        {
            "model": combo,
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
            print(f"==> smoke chat combo={combo} HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"WARN smoke chat combo={combo} HTTP {e.code}: {e.read()[:200]!r}")


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

    combo = ensure_combo_alias(opener)
    classify_combo = ensure_classifier_combo(opener)
    set_env_key(ROOT / ".env", "OMNIROUTER_DEFAULT_COMBO", COMBO_NAME)
    set_env_key(ROOT / ".env", "OMNIROUTER_CLASSIFY_COMBO", classify_combo)
    set_env_key(ROOT / ".env", "MODEL_ROUTER_CLASSIFY_MODEL", classify_combo)
    set_env_key(ROOT / ".env", "OMNIROUTER_COMBO_STRATEGY", COMBO_STRATEGY)
    set_env_key(ROOT / ".env", "OMNIROUTER_ENABLE_MEMORY", env.get("OMNIROUTER_ENABLE_MEMORY", "1"))
    enable_omni_memory(opener)

    recreate_model_router()
    time.sleep(3)
    patch_hermes_model_router(key, combo)
    verify(key, combo)
    verify(key, classify_combo)
    print(
        f"OK: first-setup omni-router complete "
        f"(chat combo={combo!r}; classify combo={classify_combo!r} with OpenCode oc/*)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read()[:300]!r}", file=sys.stderr)
        raise SystemExit(1) from e
