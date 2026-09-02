#!/usr/bin/env python3
"""First-setup OmniRouter (OmniRoute) after ENABLE_OMNIROUTER=active:

1) Login with OMNIROUTER_INITIAL_PASSWORD (else N9ROUTER_INITIAL_PASSWORD)
2) Read/create Default Key → OMNIROUTER_API_KEY
3) Ensure OpenCode provider; fill chat combo ``hermes`` with cloud ``oc/*`` members
4) Ensure classify combo ``classifier`` with cloud ``oc/*`` members
5) Ensure media combos: image-gen (image-capable), vision-ocr (supportsVision), embedding
6) Pin IMAGE_GEN_COMBO (image-gen) / OCR_MODEL (vision-ocr) from media worker state
7) Set combo strategy preference (round-robin for hermes; priority/fallback for classifier, media, embedding, web-search)
8) Ensure Search: Tavily → Firecrawl → SearXNG
9) Point Hermes at model-router; recreate router-worker for the key

Stack sends combo *names* as OpenAI ``model``. Chat = ``hermes``; classify = ``classifier``.
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
# Head-first failover (Omni ``priority``) for media, classify, embed, and search combos.
FALLBACK_COMBO_STRATEGY = os.environ.get("OMNIROUTER_FALLBACK_COMBO_STRATEGY", "priority")
IMAGE_GEN_COMBO_STRATEGY = os.environ.get("OMNIROUTER_IMAGE_GEN_COMBO_STRATEGY", FALLBACK_COMBO_STRATEGY)
VISION_OCR_COMBO_STRATEGY = os.environ.get("OMNIROUTER_VISION_OCR_COMBO_STRATEGY", FALLBACK_COMBO_STRATEGY)
CLASSIFIER_COMBO_STRATEGY = os.environ.get("OMNIROUTER_CLASSIFIER_COMBO_STRATEGY", FALLBACK_COMBO_STRATEGY)
EMBEDDING_COMBO_STRATEGY = os.environ.get("OMNIROUTER_EMBEDDING_COMBO_STRATEGY", FALLBACK_COMBO_STRATEGY)
WEB_SEARCH_COMBO_STRATEGY = os.environ.get("OMNIROUTER_WEB_SEARCH_COMBO_STRATEGY", FALLBACK_COMBO_STRATEGY)

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
    raw = path.read_text(encoding="utf-8")
    # Recover host .env pasted with literal \n sequences (template corruption).
    if "\\n" in raw:
        raw = raw.replace("\\n", "\n")
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def set_env_key(path: Path, key: str, value: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    # Quote values with spaces / shell metacharacters so `set -a; . ./.env` stays valid.
    needs_quote = any(ch in value for ch in " \t\n\"'()#$&|;<>`\\")
    if needs_quote:
        esc = value.replace("\\", "\\\\").replace('"', '\\"')
        rendered = f'"{esc}"'
    else:
        rendered = value
    line = f"{key}={rendered}"
    if re.search(rf"(?m)^{re.escape(key)}=", text):
        text = re.sub(rf"(?m)^{re.escape(key)}=.*$", line, text)
    else:
        text = text.rstrip() + "\n" + line + "\n"
    path.write_text(text, encoding="utf-8")


def clear_env_keys(path: Path, keys: list[str]) -> None:
    """Drop obsolete .env pins that conflict with combo-based routing."""
    if not path.exists() or not keys:
        return
    keyset = set(keys)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept: list[str] = []
    changed = False
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in keyset:
                changed = True
                print(f"OK: cleared obsolete {k} from .env")
                continue
        kept.append(line)
    if changed:
        path.write_text("".join(kept), encoding="utf-8")


def _provider_id_for_model(model_id: str) -> str:
    prefix = (model_id or "").split("/", 1)[0].strip().lower()
    return {
        "ollamacloud": "ollama-cloud",
        "cf": "cloudflare-ai",
        "oc": "opencode",
    }.get(prefix, prefix)


def _combo_slug(model_id: str) -> str:
    out: list[str] = []
    dash = False
    for ch in model_id or "":
        if ch.isalnum():
            out.append(ch.lower())
            dash = False
        elif not dash:
            out.append("-")
            dash = True
    return "".join(out).strip("-")[:60]


def _combo_model_entry(combo_name: str, index: int, model_id: str) -> dict:
    return {
        "id": f"{combo_name}-model-{index}-{_combo_slug(model_id)}",
        "kind": "model",
        "model": model_id,
        "providerId": _provider_id_for_model(model_id),
        "weight": 0,
    }


def _is_opencode_model_id(mid: str) -> bool:
    """Cloud OpenCode ids — not host Ollama / Alibaba leftovers."""
    m = (mid or "").strip().lower()
    return (
        m.startswith("oc/")
        or m.startswith("opencode/")
        or m.startswith("opencode-go/")
    )


def _combo_model_ids(combo: dict | None) -> list[str]:
    if not combo:
        return []
    out: list[str] = []
    for m in combo.get("models") or combo.get("members") or []:
        if isinstance(m, str) and m.strip():
            out.append(m.strip())
        elif isinstance(m, dict):
            mid = m.get("model") or m.get("fullModel") or m.get("id") or m.get("name")
            if isinstance(mid, str) and mid.strip():
                out.append(mid.strip())
    return out


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


def unblock_opencode(opener) -> None:
    """Omni may ship with ``blockedProviders: ['opencode']`` — clear it for classify."""
    try:
        _, settings = http_json(opener, "GET", f"{BASE}/api/settings")
    except Exception as e:
        print(f"WARN settings read failed: {e}")
        return
    blocked = list(settings.get("blockedProviders") or [])
    cleaned = [p for p in blocked if str(p).lower() not in {"opencode", "oc"}]
    if cleaned == blocked:
        print(f"==> blockedProviders ok ({blocked})")
        return
    print(f"==> unblock OpenCode in blockedProviders: {blocked} → {cleaned}")
    try:
        http_json(opener, "PATCH", f"{BASE}/api/settings", {"blockedProviders": cleaned})
    except Exception as e:
        print(f"WARN blockedProviders patch failed: {e}")


def ensure_opencode_provider(opener) -> dict | None:
    """Ensure an OpenCode Free connection exists; return connection dict."""
    try:
        _, data = http_json(opener, "GET", f"{BASE}/api/providers")
    except Exception as e:
        print(f"WARN providers list failed: {e}")
        return None
    conns = data.get("connections") or []
    for c in conns:
        if str(c.get("provider") or "").lower() in {"opencode", "oc"}:
            print(f"==> keep OpenCode provider connection id={c.get('id')}")
            return c if isinstance(c, dict) else None
    print("==> create OpenCode Free provider connection")
    for payload in (
        {
            "provider": "opencode",
            "authType": "apikey",
            "name": "opencode-free",
            "isActive": True,
            "proxyEnabled": False,
        },
        {"provider": "opencode", "name": "opencode-free", "isActive": True},
    ):
        try:
            status, body = http_json(opener, "POST", f"{BASE}/api/providers", payload)
        except urllib.error.HTTPError as e:
            print(f"WARN create opencode provider HTTP {e.code}: {e.read()[:200]!r}")
            continue
        if status in (200, 201):
            conn = body.get("connection") if isinstance(body, dict) else None
            print(f"==> OpenCode provider created id={(conn or {}).get('id')}")
            return conn if isinstance(conn, dict) else None
        print(f"WARN create opencode provider rejected: {body}")
    return None


def _pollinations_api_key(env: dict | None = None) -> str:
    env = env or load_env(ROOT / ".env")
    return (
        os.environ.get("POLLINATIONS_API_KEY")
        or (env.get("POLLINATIONS_API_KEY") or "")
    ).strip()


def _patch_pollinations_connection(opener, conn: dict, api_key: str) -> None:
    cid = conn.get("id")
    if not cid or not api_key:
        return
    for payload in (
        {"apiKey": api_key, "isActive": True},
        {"connection": {"apiKey": api_key, "isActive": True}},
    ):
        try:
            status, _body = http_json(opener, "PATCH", f"{BASE}/api/providers/{cid}", payload)
            if status in (200, 201):
                print(f"==> Pollinations provider apiKey refreshed id={cid}")
                return
        except Exception:
            continue


def ensure_pollinations_provider(opener, env: dict | None = None) -> dict | None:
    """Ensure Pollinations image provider (optional API key; anonymous when unset)."""
    api_key = _pollinations_api_key(env)
    try:
        _, data = http_json(opener, "GET", f"{BASE}/api/providers")
    except Exception as e:
        print(f"WARN providers list failed: {e}")
        return None
    conns = data.get("connections") or []
    for c in conns:
        if str(c.get("provider") or "").lower() == "pollinations":
            print(f"==> keep Pollinations provider connection id={c.get('id')}")
            if api_key:
                _patch_pollinations_connection(opener, c, api_key)
            return c if isinstance(c, dict) else None
    tier = "keyed" if api_key else "anonymous"
    print(f"==> create Pollinations provider connection ({tier})")
    payloads: list[dict] = []
    if api_key:
        payloads.extend(
            (
                {
                    "provider": "pollinations",
                    "authType": "apikey",
                    "name": "pollinations",
                    "isActive": True,
                    "apiKey": api_key,
                },
                {"provider": "pollinations", "name": "pollinations", "isActive": True, "apiKey": api_key},
            )
        )
    else:
        payloads.extend(
            (
                {"provider": "pollinations", "authType": "none", "name": "pollinations", "isActive": True},
                {"provider": "pollinations", "name": "pollinations", "isActive": True},
            )
        )
    for payload in payloads:
        try:
            status, body = http_json(opener, "POST", f"{BASE}/api/providers", payload)
        except urllib.error.HTTPError as e:
            print(f"WARN create pollinations provider HTTP {e.code}: {e.read()[:200]!r}")
            continue
        if status in (200, 201):
            conn = body.get("connection") if isinstance(body, dict) else None
            print(f"==> Pollinations provider created id={(conn or {}).get('id')}")
            return conn if isinstance(conn, dict) else None
        print(f"WARN create pollinations provider rejected: {body}")
    return None


def list_oc_models(opener) -> list[str]:
    """All OpenCode Free model ids (``oc/...``) from Omni catalog / fallbacks."""
    oc: list[str] = []

    # 1) Omni /api/models catalog (provider ``oc``)
    try:
        _, data = http_json(opener, "GET", f"{BASE}/api/models")
        for row in data.get("models") or []:
            if not isinstance(row, dict):
                continue
            if str(row.get("provider") or "").lower() not in {"oc", "opencode", "opencode-go"}:
                continue
            if row.get("available") is False:
                continue
            full = row.get("fullModel") or row.get("model")
            if isinstance(full, str) and full.strip():
                mid = full.strip()
                if _is_opencode_model_id(mid):
                    oc.append(mid)
                elif "/" not in mid:
                    oc.append(f"oc/{mid}")
    except Exception as e:
        print(f"WARN /api/models oc scan failed ({e})")

    # 2) Omni/9Router suggested-models helper (when present)
    if not oc:
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

    # 3) Direct OpenCode Zen catalog
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

    if not oc:
        print("WARN OpenCode catalog empty; using fallback list")
        oc = list(OPENCODE_FREE_FALLBACK)

    seen: set[str] = set()
    uniq: list[str] = []
    for mid in oc:
        if mid in seen:
            continue
        seen.add(mid)
        uniq.append(mid)
    uniq.sort(key=lambda x: (0 if x == "oc/big-pickle" else 1, x))
    return uniq








def ensure_opencode_combo(
    opener,
    *,
    name: str,
    description: str,
    member_limit: int | None = None,
    refill_if_below: int | None = None,
    strategy: str = "",
) -> str:
    """Fill Omni combo with cloud OpenCode members when empty; keep live oc/opencode/opencode-go.

    When ``refill_if_below`` is set and OpenCode member count is under that threshold
    (e.g. a single stub), refill from the OpenCode catalog like hermes/classifier.
    """
    want_strategy = (strategy or COMBO_STRATEGY).strip() or "round-robin"
    drop_probe_combos(opener)
    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == name), None)
    ids = _combo_model_ids(existing)
    cur_strategy = (existing.get("strategy") or existing.get("comboStrategy") or "").strip() if existing else ""
    good = [mid for mid in ids if _is_opencode_model_id(mid)]
    leftover = [mid for mid in ids if not _is_opencode_model_id(mid)]
    if leftover:
        print(f"==> strip leftover non-OpenCode members from {name}: {leftover[:8]!r}")
    thin = refill_if_below is not None and len(good) < refill_if_below
    if good and not thin:
        if leftover or (want_strategy and cur_strategy != want_strategy):
            models = [_combo_model_entry(name, i + 1, mid) for i, mid in enumerate(good)]
            payload = {
                "name": name,
                "models": models,
                "strategy": want_strategy,
                "description": description,
            }
            if not existing or not existing.get("id"):
                raise SystemExit(f"combo {name} missing id while updating")
            if want_strategy and cur_strategy != want_strategy:
                print(f"==> combo {name} strategy {cur_strategy!r} -> {want_strategy!r}")
            status, body = http_json(
                opener, "PUT", f"{BASE}/api/combos/{existing['id']}", payload
            )
            if status not in (200, 201):
                raise SystemExit(f"combo {name} update failed: {body}")
            if leftover:
                print(f"==> kept combo {name} OpenCode-family n={len(good)} first={good[:3]} strategy={want_strategy}")
            else:
                print(f"==> updated combo {name} strategy={want_strategy} n={len(good)}")
            return name
        print(f"==> keep combo {name} OpenCode-family n={len(good)} first={good[:3]} strategy={cur_strategy}")
        return name
    if thin:
        print(f"==> refill combo {name} OpenCode (had {len(good)} < {refill_if_below})")
    oc = [m for m in list_oc_models(opener) if _is_opencode_model_id(str(m))]
    if not oc:
        raise SystemExit(f"no OpenCode cloud models for combo {name!r}")
    if member_limit is not None and member_limit > 0:
        oc = oc[:member_limit]
    models = [_combo_model_entry(name, i + 1, mid) for i, mid in enumerate(oc)]
    payload = {
        "name": name,
        "models": models,
        "strategy": want_strategy,
        "description": description,
    }
    action = "update" if existing and existing.get("id") else "create"
    print(f"==> {action} combo {name} OpenCode n={len(models)} first={oc[:3]}")
    if existing and existing.get("id"):
        status, body = http_json(
            opener, "PUT", f"{BASE}/api/combos/{existing['id']}", payload
        )
    else:
        status, body = http_json(opener, "POST", f"{BASE}/api/combos", payload)
    if status not in (200, 201):
        raise SystemExit(f"combo {name} {action} failed: {body}")
    return name


def ensure_classifier_combo(opener) -> str:
    """Ensure classify combo ``classifier`` via Omni OpenCode cloud members."""
    return ensure_opencode_combo(
        opener,
        name=CLASSIFY_COMBO_NAME,
        description="Classify/intent combo — Omni OpenCode cloud (priority failover)",
        member_limit=5,
        strategy=CLASSIFIER_COMBO_STRATEGY,
    )


def ensure_combo_alias(opener) -> str:
    """Ensure chat combo ``hermes`` via Omni OpenCode cloud members."""
    return ensure_opencode_combo(
        opener,
        name=COMBO_NAME,
        description="Stack chat combo — Omni OpenCode cloud (round-robin)",
    )


def _search_connections(opener):
    _, data = http_json(opener, "GET", f"{BASE}/api/providers")
    connections = data.get("connections") or []
    by_prov = {}
    for c in connections:
        prov = str(c.get("provider") or "")
        if prov in ("tavily-search", "firecrawl-search", "searxng-search"):
            by_prov[prov] = c
    return by_prov


def enforce_search_priorities(opener) -> None:
    """Best-effort Omni connection priorities: Tavily=1, Firecrawl=2, SearXNG=3.

    Hermes routes search through Omni combo ``web-search`` (operator PRIORITY).
    Connection priorities are best-effort; combo members define failover order.
    """
    wanted = (
        ("tavily-search", 1),
        ("firecrawl-search", 2),
        ("searxng-search", 3),
    )
    by_prov = _search_connections(opener)
    for prov, prio in wanted:
        row = by_prov.get(prov)
        if not row or not row.get("id"):
            continue
        try:
            http_json(
                opener,
                "PUT",
                f"{BASE}/api/providers/{row['id']}",
                {"isActive": True, "priority": prio},
            )
            print(f"==> enforce {prov} priority={prio} id={row['id']}")
        except Exception as e:
            print(f"WARN enforce {prov} priority: {e}")

    by_prov = _search_connections(opener)
    for prov, prio in wanted:
        row = by_prov.get(prov)
        if not row:
            continue
        got = row.get("priority")
        active = row.get("isActive")
        print(f"==> verify {prov} priority={got} active={active}")
        if active is False:
            print(f"WARN search provider inactive: {prov}")
        if got != prio:
            print(
                f"NOTE: {prov} priority GET={got} (wanted {prio}); "
                "Omni may not persist search priorities — combo web-search owns failover"
            )


def ensure_search_providers(opener) -> None:
    """Omni UI owns search: Tavily → Firecrawl → SearXNG; block ollama-search."""
    searx_url = (
        os.environ.get("OMNIROUTER_SEARXNG_URL")
        or os.environ.get("SEARXNG_URL")
        or "http://searxng:8080"
    ).rstrip("/")
    print(f"==> ensure Omni search providers (SearXNG base={searx_url})")

    by_prov = _search_connections(opener)
    tavily = by_prov.get("tavily-search")
    firecrawl = by_prov.get("firecrawl-search")
    searx = by_prov.get("searxng-search")

    if tavily and tavily.get("id"):
        try:
            http_json(
                opener,
                "PUT",
                f"{BASE}/api/providers/{tavily['id']}",
                {"isActive": True, "priority": 1},
            )
            print(f"==> tavily-search priority=1 id={tavily['id']}")
        except Exception as e:
            print(f"WARN tavily priority: {e}")
    else:
        print("NOTE: no tavily-search connection — add API key in Omni Providers → Search")

    if firecrawl and firecrawl.get("id"):
        try:
            http_json(
                opener,
                "PUT",
                f"{BASE}/api/providers/{firecrawl['id']}",
                {"isActive": True, "priority": 2},
            )
            print(f"==> firecrawl-search priority=2 id={firecrawl['id']}")
        except Exception as e:
            print(f"WARN firecrawl priority: {e}")
    else:
        print("NOTE: no firecrawl-search connection — add API key in Omni Providers → Search")

    # Omni stores local SearXNG URL in providerSpecificData.baseUrl (SSRF-aware path).
    # Do not rely on this PUT for priority — Omni may reset it; enforce_search_priorities
    # runs a minimal priority-only pass afterward.
    cid = None
    searx_body = {
        "provider": "searxng-search",
        "name": "local-searxng",
        "isActive": True,
        "priority": 3,
        "apiKey": "local",
        "baseUrl": searx_url,
        "providerSpecificData": {"baseUrl": searx_url},
    }
    if searx and searx.get("id"):
        try:
            http_json(opener, "PUT", f"{BASE}/api/providers/{searx['id']}", searx_body)
            cid = searx["id"]
            print(f"==> update searxng-search id={cid}")
        except Exception as e:
            print(f"WARN searxng update: {e}")
            cid = searx.get("id")
    else:
        try:
            status, body = http_json(opener, "POST", f"{BASE}/api/providers", searx_body)
            cid = (body.get("connection") or body).get("id")
            print(f"==> create searxng-search HTTP {status} id={cid}")
            if cid:
                http_json(
                    opener,
                    "PUT",
                    f"{BASE}/api/providers/{cid}",
                    {
                        "apiKey": "local",
                        "isActive": True,
                        "priority": 3,
                        "providerSpecificData": {"baseUrl": searx_url},
                    },
                )
        except Exception as e:
            print(f"WARN searxng create: {e}")
            cid = None

    if cid:
        try:
            status, body = http_json(opener, "POST", f"{BASE}/api/providers/{cid}/test")
            print(f"==> searxng test valid={body.get('valid')} err={body.get('error')}")
        except Exception as e:
            print(f"WARN searxng test: {e}")

    enforce_search_priorities(opener)

    # Drop accidental chat combo named websearch that embeds search providers as models.
    try:
        _, combos = http_json(opener, "GET", f"{BASE}/api/combos")
        for c in combos.get("combos") or []:
            if (c.get("name") or "") != "websearch":
                continue
            models = c.get("models") or []
            if any(
                "search" in str(m.get("providerId") or m.get("model") or "").lower()
                for m in models
                if isinstance(m, dict)
            ):
                print(f"==> delete misleading chat combo websearch id={c.get('id')}")
                http_json(opener, "DELETE", f"{BASE}/api/combos/{c['id']}")
    except Exception as e:
        print(f"WARN websearch combo cleanup: {e}")

    # Prefer Tavily/Firecrawl/SearXNG over built-in ollama-search for default /v1/search.
    try:
        _, settings = http_json(opener, "GET", f"{BASE}/api/settings")
        blocked = list(settings.get("blockedProviders") or [])
        if "ollama-search" not in blocked:
            blocked.append("ollama-search")
            http_json(opener, "PUT", f"{BASE}/api/settings", {"blockedProviders": blocked})
            print("==> blockedProviders += ollama-search")
        else:
            print("==> ollama-search already blocked")
    except Exception as e:
        print(f"WARN blockedProviders: {e}")


WEB_SEARCH_COMBO_NAME = "web-search"
_WEB_SEARCH_MEMBER_ORDER = ("tavily-search", "firecrawl-search", "searxng-search")


def list_web_search_combo_members(opener) -> list[str]:
    """Ordered search provider ids for combo web-search (Tavily -> Firecrawl -> SearXNG)."""
    by_prov = _search_connections(opener)
    out: list[str] = []
    for prov in _WEB_SEARCH_MEMBER_ORDER:
        row = by_prov.get(prov)
        if not row or not row.get("id"):
            continue
        if row.get("isActive") is False:
            continue
        out.append(prov)
    return out


def ensure_web_search_omni_combo(opener) -> None:
    """Seed combo ``web-search`` when empty; fix strategy to priority without reordering members."""
    members = list_web_search_combo_members(opener)
    if not members:
        print("WARN: no active search providers — skip web-search combo")
        return
    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == WEB_SEARCH_COMBO_NAME), None)
    cur = _combo_model_ids(existing)
    if not cur:
        print(f"==> seed combo {WEB_SEARCH_COMBO_NAME} members={members!r}")
    _put_or_create_combo(
        opener,
        name=WEB_SEARCH_COMBO_NAME,
        description="Web search — Tavily, Firecrawl, local SearXNG (priority failover)",
        model_ids=members,
        force=not cur,
        strategy=WEB_SEARCH_COMBO_STRATEGY,
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


STACK_API_KEY_COMBOS = (
    "hermes",
    "classifier",
    "image-gen",
    "vision-ocr",
    "embedding",
    "web-search",
)


def _row_has_image_modality(row: dict) -> bool:
    mods = row.get("modalities") or row.get("output_modalities") or []
    if isinstance(mods, list):
        return any(str(m).lower() == "image" for m in mods)
    return False


_STACK_COMBO_NAMES = frozenset(
    {"image-gen", "hermes", "classifier", "vision-ocr", "embedding", "web-search"}
)


def _row_api_format(row: dict) -> str:
    return str(row.get("apiFormat") or row.get("api_format") or "").strip().lower()


def _row_provider(row: dict) -> str:
    return str(row.get("provider") or row.get("providerId") or "").strip().lower()


def _row_supported_endpoints(row: dict) -> list[str]:
    eps = row.get("supportedEndpoints") or row.get("supported_endpoints") or []
    if isinstance(eps, list):
        return [str(e).strip().lower() for e in eps if str(e).strip()]
    return []


def _row_supports_images_endpoint(row: dict) -> bool:
    return "images" in _row_supported_endpoints(row)


def _row_supports_chat_endpoint(row: dict) -> bool:
    eps = _row_supported_endpoints(row)
    return "chat" in eps if eps else False


def _is_chat_only_catalog_row(row: dict) -> bool:
    """Chat/completions models must not land in image-gen (even when id looks image-related)."""
    eps = _row_supported_endpoints(row)
    if eps:
        return "chat" in eps and "images" not in eps
    if _is_opencode_model_id(str(row.get("id") or "")):
        return True
    caps = row.get("capabilities") if isinstance(row.get("capabilities"), dict) else {}
    return caps.get("image_generation") is False


def _is_image_output_model(row: dict) -> bool:
    """True only when Omni catalog marks the model for /images/generations."""
    mid = str(row.get("id") or "").strip()
    if not mid or mid.lower() in _STACK_COMBO_NAMES:
        return False
    if row.get("available") is False:
        return False
    if _is_chat_only_catalog_row(row):
        return False
    if _row_supports_images_endpoint(row):
        return True
    if _row_api_format(row) == "images-generations":
        return True
    if str(row.get("type") or "").strip().lower() == "image":
        return True
    caps = row.get("capabilities") if isinstance(row.get("capabilities"), dict) else {}
    if caps.get("image_generation") is True:
        return True
    if caps.get("image_generation") is False:
        return False
    if _row_has_image_modality(row):
        return False
    return False


def _catalog_row_by_id(catalog: list[dict], mid: str) -> dict | None:
    want = (mid or "").strip()
    if not want:
        return None
    for row in catalog:
        if str(row.get("id") or "").strip() == want:
            return row
    return None


def _is_image_gen_model_id(mid: str, catalog: list[dict] | None = None) -> bool:
    row = _catalog_row_by_id(catalog or [], mid)
    if row is None:
        return False
    return _is_image_output_model(row)


def _is_bad_image_gen_combo_member(mid: str, catalog: list[dict] | None = None) -> bool:
    return not _is_image_gen_model_id(mid, catalog)


def _rank_image_gen_row(row: dict) -> tuple:
    """Prefer catalog rows explicitly wired to images/generations (provider-agnostic)."""
    mid = str(row.get("id") or "").lower()
    tier = 4
    if _row_supports_images_endpoint(row) and _row_api_format(row) == "images-generations":
        tier = 0
    elif _row_supports_images_endpoint(row) or str(row.get("type") or "").strip().lower() == "image":
        tier = 1
    elif _is_image_output_model(row):
        tier = 2
    provider = _row_provider(row)
    provider_bonus = 0 if provider == "pollinations" else 1
    return (tier, provider_bonus, mid)


def _resolve_image_gen_head(
    image_ids: list[str],
    env: dict[str, str] | None = None,
    catalog: list[dict] | None = None,
) -> str:
    env = env or {}
    override = (env.get("IMAGE_GEN_HEAD_MEMBER") or os.environ.get("IMAGE_GEN_HEAD_MEMBER") or "").strip().strip('"')
    if override and override in image_ids and _is_image_gen_model_id(override, catalog):
        return override
    return image_ids[0] if image_ids else ""


def ensure_api_key_allows_combos(opener, existing_key: str) -> None:
    """Omni treats allowedCombos=[] as deny-all for combo names — pin stack combos.

    Empty allowlists block hermes/classifier/image-gen even when modelAccessMode=all.
    """
    _, data = http_json(opener, "GET", f"{BASE}/api/keys")
    keys = data.get("keys") or []
    want = list(STACK_API_KEY_COMBOS)
    # Also allow any existing stack combos present in Omni.
    try:
        _, combos = http_json(opener, "GET", f"{BASE}/api/combos")
        for c in combos.get("combos") or []:
            name = (c.get("name") or "").strip()
            if name and name not in want:
                # Keep operator combos out of the pin set; only ensure stack names.
                pass
    except Exception as e:
        print(f"WARN list combos for key ACL: {e}")

    prefix = (existing_key or "").strip()[:12]
    target = None
    for row in keys:
        if not isinstance(row, dict):
            continue
        masked = str(row.get("key") or row.get("keyPrefix") or "")
        name = str(row.get("name") or "")
        if prefix and prefix in masked.replace("*", ""):
            target = row
            break
        if name in {"assistant-stack", "Default Key"} and target is None:
            target = row
    if not target or not target.get("id"):
        print("WARN: no API key row to patch allowedCombos")
        return
    cur = [str(x) for x in (target.get("allowedCombos") or []) if str(x).strip()]
    merged = list(cur)
    for name in want:
        if name not in merged:
            merged.append(name)
    if set(merged) == set(cur) and cur:
        print(f"==> keep API key allowedCombos n={len(cur)}")
        return
    kid = target["id"]
    status, body = http_json(
        opener, "PATCH", f"{BASE}/api/keys/{kid}", {"allowedCombos": merged}
    )
    if status not in (200, 201):
        raise SystemExit(f"API key allowedCombos patch failed: {body}")
    print(f"OK: API key allowedCombos={merged}")


def _media_worker_active(env: dict[str, str]) -> bool:
    """True only when media worker flag is ``active``."""
    for key in ("ENABLE_MEDIA_FILE", "WORKER_MEDIA_FILE"):
        v = (env.get(key) or os.environ.get(key) or "").strip().lower()
        if v in {"active", "1", "true", "yes", "on"}:
            return True
    return False


def pin_media_combos(env: dict[str, str]) -> None:
    """Pin media combo *names* when the media worker is active.

    image-gen and vision-ocr keep their own Omni members — never remap to hermes.
    """
    env_path = ROOT / ".env"
    active = _media_worker_active(env)
    if not active:
        cur = (env.get("ENABLE_MEDIA_FILE") or "").strip().lower()
        if cur == "active":
            set_env_key(env_path, "ENABLE_MEDIA_FILE", "inactive")
            env["ENABLE_MEDIA_FILE"] = "inactive"
            print("OK: pinned ENABLE_MEDIA_FILE=inactive")
        return
    if (env.get("ENABLE_MEDIA_FILE") or "").strip().lower() != "active":
        set_env_key(env_path, "ENABLE_MEDIA_FILE", "active")
        env["ENABLE_MEDIA_FILE"] = "active"
        print("OK: pinned ENABLE_MEDIA_FILE=active")
    pins = {
        "IMAGE_GEN_COMBO": env.get("OMNIROUTER_IMAGE_COMBO") or "image-gen",
        "OCR_MODEL": env.get("OMNIROUTER_VISION_COMBO") or "vision-ocr",
        "OCR_VISION": "active",
        "EMBED_MODEL": env.get("OMNIROUTER_EMBED_COMBO") or "embedding",
        "OMNIROUTER_IMAGE_COMBO": env.get("OMNIROUTER_IMAGE_COMBO") or "image-gen",
        "OMNIROUTER_VISION_COMBO": env.get("OMNIROUTER_VISION_COMBO") or "vision-ocr",
        "OMNIROUTER_EMBED_COMBO": env.get("OMNIROUTER_EMBED_COMBO") or "embedding",
    }
    for key, want in pins.items():
        cur = (env.get(key) or "").strip()
        if cur == want:
            continue
        set_env_key(env_path, key, want)
        env[key] = want
        print(f"OK: pinned {key}={want}")


def _stack_env_paths() -> list[Path]:
    """Stack + shared data .env files (Hermes replicas read shared copy)."""
    shared = (
        os.environ.get("HERMES_SHARED_DATA_DIR")
        or os.environ.get("HERMES_DATA_DIR")
        or os.environ.get("ASSISTANT_DATA_DIR")
        or "/data/assistant"
    ).strip()
    paths = [ROOT / ".env", Path(shared) / ".env"]
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _clear_stack_env_keys(keys: list[str]) -> None:
    for path in _stack_env_paths():
        clear_env_keys(path, keys)


def _set_stack_env_key(key: str, value: str) -> None:
    for path in _stack_env_paths():
        set_env_key(path, key, value)


def _v1_models(api_key: str) -> list[dict]:
    req = urllib.request.Request(
        f"{BASE}/v1/models",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode() or "{}")
    rows = data.get("data") or []
    return [r for r in rows if isinstance(r, dict)]


def _rank_image_gen_model(mid: str, catalog: list[dict] | None = None) -> tuple:
    row = _catalog_row_by_id(catalog or [], mid)
    if row is not None:
        return _rank_image_gen_row(row)
    return (9, mid.lower())


def list_image_gen_models(api_key: str) -> list[str]:
    """Models Omni catalog marks for /images/generations (no id-prefix guessing)."""
    rows = _v1_models(api_key)
    found = [r for r in rows if _is_image_output_model(r)]
    found.sort(key=_rank_image_gen_row)
    return [str(r.get("id") or "").strip() for r in found if str(r.get("id") or "").strip()][:8]


def _order_image_gen_combo_members(image_ids: list[str], head: str) -> list[str]:
    if not head or head not in image_ids:
        return image_ids
    return [head] + [m for m in image_ids if m != head]


def _omni_model_row_id(row: dict) -> str:
    for key in ("fullModel", "model", "id"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _row_supports_vision_input(row: dict) -> bool:
    mods = row.get("input_modalities") or row.get("modalities") or []
    if isinstance(mods, list):
        return any(str(m).lower() in {"image", "vision"} for m in mods)
    return False


def _is_vision_capable_model_row(row: dict) -> bool:
    """Chat models that accept image input for OCR (not supportsVision-only blind ids)."""
    mid = _omni_model_row_id(row)
    if not mid or mid.lower() in _STACK_COMBO_NAMES:
        return False
    if not row.get("supportsVision"):
        return False
    if row.get("available") is False:
        return False
    eps = _row_supported_endpoints(row)
    if eps and "chat" not in eps:
        return False
    caps = row.get("capabilities") if isinstance(row.get("capabilities"), dict) else {}
    if caps.get("vision") is False:
        return False
    if row.get("modalities") or row.get("input_modalities") or eps:
        return _row_supports_vision_input(row)
    return caps.get("vision") is True


def _rank_vision_row(row: dict) -> tuple:
    mid = _omni_model_row_id(row).lower()
    caps = row.get("capabilities") if isinstance(row.get("capabilities"), dict) else {}
    tier = 3
    if caps.get("vision") is True and _row_supports_vision_input(row):
        tier = 0
    elif _row_supports_vision_input(row):
        tier = 1
    elif row.get("supportsVision"):
        tier = 2
    provider = _row_provider(row)
    oc_bonus = 0 if provider in {"oc", "opencode", "opencode-go"} else 1
    return (tier, oc_bonus, mid)


def _is_vision_capable_model_id(mid: str, catalog: list[dict] | None = None) -> bool:
    want = (mid or "").strip()
    if not want:
        return False
    for row in catalog or []:
        if _omni_model_row_id(row) == want:
            return _is_vision_capable_model_row(row)
    return False


def _omni_admin_catalog_rows(opener) -> list[dict]:
    _, data = http_json(opener, "GET", f"{BASE}/api/models")
    return [r for r in (data.get("models") or []) if isinstance(r, dict)]


def list_vision_models(opener) -> list[str]:
    """Multimodal chat models for OCR vision fallback (catalog image-input capability)."""
    rows = _omni_admin_catalog_rows(opener)
    found = [r for r in rows if isinstance(r, dict) and _is_vision_capable_model_row(r)]
    found.sort(key=_rank_vision_row)
    out: list[str] = []
    for row in found:
        mid = _omni_model_row_id(row)
        if mid and mid not in out:
            out.append(mid)
    return out[:10]


def _is_embedding_model_id(mid: str) -> bool:
    low = (mid or "").strip().lower()
    if not low or low == "embedding":
        return False
    # OpenCode shell members are allowed as first-setup defaults even without
    # "embed" in the id (operator may later swap to an embed-capable model).
    if _is_opencode_model_id(low):
        return True
    if "embed" in low:
        return True
    return False


def _is_embedding_output_model(row: dict) -> bool:
    mid = str(row.get("id") or "").strip()
    if not mid or mid.lower() == "embedding":
        return False
    low = mid.lower()
    caps = row.get("capabilities") if isinstance(row.get("capabilities"), dict) else {}
    mods = row.get("modalities") or row.get("output_modalities") or []
    if caps.get("embedding") is True:
        return True
    if isinstance(mods, list) and any(str(m).lower() == "embedding" for m in mods):
        return True
    return "embed" in low


def list_embedding_models(api_key: str, opener=None) -> list[str]:
    """Models for /v1/embeddings — OpenCode-first single member (one vector size)."""
    rows = _v1_models(api_key)
    found = [str(r.get("id")) for r in rows if _is_embedding_output_model(r) and r.get("id")]
    oc_embed = [m for m in found if _is_opencode_model_id(m)]
    if oc_embed:
        return [oc_embed[0]]

    # No embed-capable OpenCode id in catalog — seed one OpenCode shell (stack default).
    oc: list[str] = []
    if opener is not None:
        try:
            oc = [m for m in list_oc_models(opener) if _is_opencode_model_id(str(m))]
        except Exception as e:
            print(f"WARN list_oc_models for embedding: {e}")
    if not oc:
        oc = [m for m in OPENCODE_FREE_FALLBACK if _is_opencode_model_id(m)]
    if oc:
        print(
            f"WARN: no OpenCode embed-capable catalog model — "
            f"seeding OpenCode shell {oc[0]!r}"
        )
        return [oc[0]]

    # Last resort: non-OpenCode embed (only when OpenCode catalog is empty).
    preferred_fallback = [
        "gemini/gemini-embedding-001",
        "openrouter/openai/text-embedding-3-small",
        "openrouter/qwen/qwen3-embedding-8b",
    ]
    for mid in preferred_fallback:
        if mid in found:
            print(f"WARN: embedding fallback to non-OpenCode {mid!r}")
            return [mid]
    return found[:1]


def _put_or_create_combo(
    opener,
    *,
    name: str,
    description: str,
    model_ids: list[str],
    force: bool,
    strategy: str = "",
) -> str:
    if not model_ids:
        raise SystemExit(f"combo {name}: no candidate models")
    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == name), None)
    current = _combo_model_ids(existing)
    want_strategy = (strategy or COMBO_STRATEGY).strip() or "round-robin"
    cur_strategy = (existing.get("strategy") or existing.get("comboStrategy") or "").strip() if existing else ""
    if existing and current and not force:
        if want_strategy and cur_strategy != want_strategy:
            print(f"==> combo {name} strategy {cur_strategy!r} -> {want_strategy!r}")
            model_ids = list(current)
        elif not want_strategy or cur_strategy == want_strategy:
            print(f"==> keep combo {name} n={len(current)} first={current[:3]} strategy={cur_strategy}")
            return name
    models = [_combo_model_entry(name, i + 1, mid) for i, mid in enumerate(model_ids)]
    payload = {
        "name": name,
        "models": models,
        "strategy": want_strategy,
        "description": description,
    }
    if existing and existing.get("id"):
        status, body = http_json(
            opener, "PUT", f"{BASE}/api/combos/{existing['id']}", payload
        )
        action = "update"
    else:
        status, body = http_json(opener, "POST", f"{BASE}/api/combos", payload)
        action = "create"
    if status not in (200, 201):
        raise SystemExit(f"combo {name} {action} failed: {body}")
    print(f"OK: {action} combo {name} n={len(model_ids)} first={model_ids[:3]} strategy={want_strategy}")
    return name


def _images_generations_provider_nodes(opener) -> list[dict]:
    try:
        _, data = http_json(opener, "GET", f"{BASE}/api/provider-nodes")
    except Exception as e:
        print(f"WARN provider-nodes list failed: {e}")
        return []
    out: list[dict] = []
    for node in data.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        if str(node.get("apiType") or "").strip().lower() == "images-generations":
            out.append(node)
    return out


def _catalog_rows_for_provider(catalog: list[dict], provider: str) -> list[dict]:
    want = (provider or "").strip().lower()
    if not want:
        return []
    out: list[dict] = []
    for row in catalog:
        if _row_provider(row) == want:
            out.append(row)
            continue
        mid = str(row.get("id") or "").strip().lower()
        if mid.startswith(f"{want}/"):
            out.append(row)
    return out


def _provider_model_local_id(provider: str, full_id: str) -> str:
    low = (full_id or "").strip()
    prefix = f"{(provider or '').strip()}/"
    if prefix and low.lower().startswith(prefix.lower()):
        return low[len(prefix) :]
    return low


def ensure_provider_image_models(opener, api_key: str) -> None:
    """Register/repair custom provider models for /images/generations (catalog-driven)."""
    nodes = _images_generations_provider_nodes(opener)
    if not nodes:
        print("NOTE: no images-generations provider node — skip custom image-model registration")
        return
    catalog = _v1_models(api_key)
    for node in nodes:
        provider = str(node.get("id") or "").strip()
        if not provider:
            continue
        state = _custom_models_by_provider(opener, provider)
        for model_id, existing in state.items():
            action = _custom_image_model_action(existing)
            if not action:
                continue
            body = {
                "provider": provider,
                "modelId": model_id,
                "modelName": existing.get("modelName") or model_id,
                "apiFormat": "images-generations",
                "supportedEndpoints": ["images"],
            }
            status, resp = http_json(opener, "PUT", f"{BASE}/api/provider-models", body)
            if status in (200, 201):
                print(f"OK: fix custom image model {provider[:8]}…/{model_id} (images-generations)")
            else:
                print(f"WARN fix {model_id} on {provider[:8]}…: {str(resp)[:200]}")
        for row in _catalog_rows_for_provider(catalog, provider):
            if not _is_image_output_model(row):
                continue
            full_id = str(row.get("id") or "").strip()
            local_id = _provider_model_local_id(provider, full_id)
            if not local_id or local_id in state or full_id in state:
                continue
            action = _custom_image_model_action(state.get(local_id))
            if not action:
                continue
            body = {
                "provider": provider,
                "modelId": local_id,
                "modelName": local_id,
                "apiFormat": "images-generations",
                "supportedEndpoints": ["images"],
            }
            status, resp = http_json(opener, "POST", f"{BASE}/api/provider-models", body)
            if status in (200, 201):
                print(f"OK: add custom image model {provider[:8]}…/{local_id} (images-generations)")
            else:
                print(f"WARN add {local_id} on {provider[:8]}…: {str(resp)[:200]}")


def _custom_models_by_provider(opener, provider: str) -> dict[str, dict]:
    query = urllib.parse.urlencode({"provider": provider})
    try:
        _, data = http_json(opener, "GET", f"{BASE}/api/provider-models?{query}")
    except Exception as e:
        print(f"WARN provider-models GET failed for {provider[:8]}…: {e}")
        return {}
    models = data.get("models")
    if isinstance(models, dict):
        bucket = models.get(provider) or []
    elif isinstance(models, list):
        bucket = models
    else:
        bucket = []
    return {
        str(row.get("id")): row
        for row in bucket
        if isinstance(row, dict) and row.get("id")
    }


def _custom_image_model_action(existing: dict | None) -> str:
    if not existing:
        return "add"
    endpoints = [str(e) for e in (existing.get("supportedEndpoints") or [])]
    api_format = str(existing.get("apiFormat") or "").strip()
    if "images" in endpoints and api_format == "images-generations":
        return ""
    return "fix"


def ensure_media_combos(opener, api_key: str, env: dict[str, str]) -> None:
    """Seed image-gen / vision-ocr / embedding combos; refill when chat-only members leak in."""
    catalog = _v1_models(api_key)
    image_ids = list_image_gen_models(api_key)
    if not image_ids:
        raise SystemExit(
            "no images-capable models in Omni catalog — connect an images-generations provider"
        )
    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    combos = {c.get("name"): c for c in (data.get("combos") or []) if isinstance(c, dict)}
    cur_img = _combo_model_ids(combos.get("image-gen"))
    bad_img = [m for m in cur_img if _is_bad_image_gen_combo_member(m, catalog)]
    head = _resolve_image_gen_head(image_ids, env, catalog)
    want_ids = _order_image_gen_combo_members(image_ids, head)
    need_img = (
        (not cur_img)
        or bool(bad_img)
        or not set(cur_img).intersection(set(image_ids))
        or cur_img != want_ids
    )
    if bad_img:
        print(
            f"==> image-gen has invalid members {bad_img[:6]!r} "
            f"(chat-only / unsupported for /images/generations) — refilling"
        )
    elif not cur_img:
        print(f"==> seed combo image-gen from catalog first={want_ids[:3]!r}")
    _put_or_create_combo(
        opener,
        name="image-gen",
        description="Image generation — diffusion /images/generations only",
        model_ids=want_ids,
        force=need_img,
        strategy=IMAGE_GEN_COMBO_STRATEGY,
    )
    if head:
        _set_stack_env_key("IMAGE_GEN_HEAD_MEMBER", head)
        print(f"OK: pinned IMAGE_GEN_HEAD_MEMBER={head}")

    vision_catalog = _omni_admin_catalog_rows(opener)
    vision_ids = list_vision_models(opener)
    if not vision_ids:
        vision_ids = list_oc_models(opener)[:5] or list(OPENCODE_FREE_FALLBACK[:5])
        print(f"WARN no vision-capable catalog; seeding vision-ocr with OpenCode {vision_ids[:3]}")
    cur_vis = _combo_model_ids(combos.get("vision-ocr"))
    bad_vis = [m for m in cur_vis if not _is_vision_capable_model_id(m, vision_catalog)]
    need_vis = (not cur_vis) or bool(bad_vis) or cur_vis != vision_ids
    if bad_vis:
        print(f"==> vision-ocr has blind members {bad_vis[:6]!r} — refilling")
    elif not cur_vis:
        print(f"==> seed combo vision-ocr from catalog first={vision_ids[:3]!r}")
    _put_or_create_combo(
        opener,
        name="vision-ocr",
        description="Vision OCR — multimodal chat (catalog image-input)",
        model_ids=vision_ids,
        force=need_vis,
        strategy=VISION_OCR_COMBO_STRATEGY,
    )

    emb_ids = list_embedding_models(api_key, opener=opener)
    cur_emb = _combo_model_ids(combos.get("embedding"))
    if emb_ids:
        if not cur_emb:
            print(f"==> seed combo embedding {emb_ids!r}")
        _put_or_create_combo(
            opener,
            name="embedding",
            description="Embeddings — Omni /v1/embeddings",
            model_ids=emb_ids,
            force=not cur_emb,
            strategy=EMBEDDING_COMBO_STRATEGY,
        )
    elif not combos.get("embedding"):
        emb = list_oc_models(opener)[:1] or list(OPENCODE_FREE_FALLBACK[:1])
        _put_or_create_combo(
            opener,
            name="embedding",
            description="Embeddings — Omni /v1/embeddings (shell)",
            model_ids=emb,
            force=True,
            strategy=EMBEDDING_COMBO_STRATEGY,
        )
        print("WARN: no embed-capable catalog models — seeded shell only")
    else:
        print("OK: combo embedding exists (operator-owned members)")


def assert_combo_oc_only(opener, name: str) -> None:
    """Fail setup if hermes/classifier contain non-OpenCode members."""
    _, data = http_json(opener, "GET", f"{BASE}/api/combos")
    combos = data.get("combos") or []
    combo = next((c for c in combos if (c.get("name") or "") == name), None)
    if not combo:
        raise SystemExit(f"combo {name!r} missing after OpenCode fill")
    ids = _combo_model_ids(combo)
    if not ids:
        raise SystemExit(f"combo {name!r} has zero members after OpenCode fill")
    bad = [mid for mid in ids if not _is_opencode_model_id(mid)]
    if bad:
        raise SystemExit(
            f"combo {name!r} has non-OpenCode members {bad[:8]!r} — expected oc/opencode/opencode-go"
        )
    print(f"OK: combo {name} OpenCode-only n={len(ids)} first={ids[:3]}")


def main() -> int:
    env = load_env(ROOT / ".env")
    omni_flag = (env.get("ENABLE_OMNIROUTER") or "inactive").strip().lower()
    if omni_flag in {"1", "true", "yes", "on"}:
        set_env_key(ROOT / ".env", "ENABLE_OMNIROUTER", "active")
        env["ENABLE_OMNIROUTER"] = "active"
        omni_flag = "active"
        print("OK: migrated ENABLE_OMNIROUTER to active")
    if omni_flag != "active":
        print("SKIP: ENABLE_OMNIROUTER is not active")
        return 0
    password = env.get("OMNIROUTER_INITIAL_PASSWORD") or env.get("N9ROUTER_INITIAL_PASSWORD") or ""
    if not password:
        raise SystemExit("OMNIROUTER_INITIAL_PASSWORD / N9ROUTER_INITIAL_PASSWORD empty")

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    key = fetch_default_key(opener, password, env.get("OMNIROUTER_API_KEY", ""))
    set_env_key(ROOT / ".env", "OMNIROUTER_API_KEY", key)
    print(f"==> wrote OMNIROUTER_API_KEY to {ROOT / '.env'}")

    unblock_opencode(opener)
    ensure_opencode_provider(opener)
    ensure_pollinations_provider(opener, env)
    ensure_provider_image_models(opener, key)
    combo = ensure_combo_alias(opener)
    classify_combo = ensure_classifier_combo(opener)
    assert_combo_oc_only(opener, combo)
    assert_combo_oc_only(opener, classify_combo)
    ensure_combo_round_robin(opener)
    ensure_search_providers(opener)
    ensure_web_search_omni_combo(opener)
    ensure_media_combos(opener, key, env)
    ensure_api_key_allows_combos(opener, key)
    pin_media_combos(env)
    set_env_key(ROOT / ".env", "OMNIROUTER_DEFAULT_COMBO", COMBO_NAME)
    set_env_key(ROOT / ".env", "OMNIROUTER_CLASSIFY_COMBO", classify_combo)
    set_env_key(ROOT / ".env", "MODEL_ROUTER_CLASSIFY_MODEL", classify_combo)
    set_env_key(ROOT / ".env", "OMNIROUTER_COMBO_STRATEGY", COMBO_STRATEGY)
    set_env_key(ROOT / ".env", "OMNIROUTER_FALLBACK_COMBO_STRATEGY", FALLBACK_COMBO_STRATEGY)
    set_env_key(ROOT / ".env", "OMNIROUTER_VISION_OCR_COMBO_STRATEGY", VISION_OCR_COMBO_STRATEGY)
    set_env_key(ROOT / ".env", "OMNIROUTER_CLASSIFIER_COMBO_STRATEGY", CLASSIFIER_COMBO_STRATEGY)
    set_env_key(ROOT / ".env", "OMNIROUTER_EMBEDDING_COMBO_STRATEGY", EMBEDDING_COMBO_STRATEGY)
    set_env_key(ROOT / ".env", "OMNIROUTER_WEB_SEARCH_COMBO_STRATEGY", WEB_SEARCH_COMBO_STRATEGY)
    set_env_key(ROOT / ".env", "OMNIROUTER_ENABLE_MEMORY", env.get("OMNIROUTER_ENABLE_MEMORY", "active"))
    # Hermes-facing Router Worker: combo web-search via Omni only (no direct adapter chain).
    _clear_stack_env_keys(
        ["OMNIROUTER_SEARCH_PROVIDERS", "WEB_SEARCH_COMBO_PATH", "WEB_BACKENDS"],
    )
    env.pop("WEB_BACKENDS", None)
    web_combo = (env.get("MODEL_ROUTER_WEB_SEARCH_COMBO") or env.get("WEB_SEARCH_COMBO") or WEB_SEARCH_COMBO_NAME).strip()
    if not web_combo:
        web_combo = WEB_SEARCH_COMBO_NAME
    for key_name, val in (
        ("OMNIROUTER_WEB_SEARCH_COMBO", web_combo),
        ("WEB_SEARCH_COMBO", web_combo),
        ("MODEL_ROUTER_WEB_SEARCH_COMBO", web_combo),
    ):
        if (env.get(key_name) or "").strip() != val:
            set_env_key(ROOT / ".env", key_name, val)
            env[key_name] = val
            print(f"OK: pinned {key_name}={val}")
    enable_omni_memory(opener)

    recreate_model_router()
    time.sleep(3)
    patch_hermes_model_router(key, combo)
    # Verify hermes combo via Omni /v1/chat/completions (OpenCode cloud members).
    verify(key, combo)
    print(
        f"OK: first-setup omni-router complete "
        f"(hermes+classifier OpenCode; image-gen image-capable; vision-ocr multimodal; "
        f"classify→{classify_combo!r}; combo web-search Tavily->Firecrawl->SearXNG)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read()[:300]!r}", file=sys.stderr)
        raise SystemExit(1) from e
