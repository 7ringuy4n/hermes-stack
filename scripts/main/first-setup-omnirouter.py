#!/usr/bin/env python3
"""First-setup OmniRouter (OmniRoute) after ENABLE_OMNIROUTER=1:

1) Login with OMNIROUTER_INITIAL_PASSWORD (else N9ROUTER_INITIAL_PASSWORD)
2) Read/create Default Key → OMNIROUTER_API_KEY
3) Ensure chat combo alias exists (OMNIROUTER_DEFAULT_COMBO, default ``hermes``)
   — **empty members**; operator adds models in Omni Combos UI (no OpenCode defaults)
4) Ensure classify combo ``classifier`` — **empty members** (same rule)
5) Set combo strategy preference (round-robin)
6) Ensure Search providers: Tavily (1) → Firecrawl (2) → local SearXNG (3);
   block ollama-search so Omni /v1/search owns web search
7) Point Hermes at model-router; recreate router-worker for the key

Stack code sends combo *names* as OpenAI ``model``. Chat uses ``hermes``;
classify uses ``classifier``. Web search: Hermes → model-router /v1/search → Omni.
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

# Local helpers (omnirouter_qwen) live next to this script.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from omnirouter_qwen import (
        ensure_alibaba_qwen_provider as _ensure_alibaba_qwen_provider,
        ensure_combo_qwen_fast as _ensure_combo_qwen_fast,
        ensure_combo_qwen_first as _ensure_combo_qwen_first,
    )
except ImportError:
    from omnirouter_qwen import (  # type: ignore
        ensure_alibaba_qwen_provider as _ensure_alibaba_qwen_provider,
        ensure_combo_qwen_fast as _ensure_combo_qwen_fast,
        ensure_combo_qwen_first as _ensure_combo_qwen_first,
    )

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


def list_oc_models(opener) -> list[str]:
    """All OpenCode Free model ids (``oc/...``) from Omni catalog / fallbacks."""
    oc: list[str] = []

    # 1) Omni /api/models catalog (provider ``oc``)
    try:
        _, data = http_json(opener, "GET", f"{BASE}/api/models")
        for row in data.get("models") or []:
            if not isinstance(row, dict):
                continue
            if str(row.get("provider") or "").lower() not in {"oc", "opencode"}:
                continue
            if row.get("available") is False:
                continue
            full = row.get("fullModel") or row.get("model")
            if isinstance(full, str) and full.strip():
                mid = full.strip()
                oc.append(mid if mid.startswith("oc/") else f"oc/{mid}")
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



def ensure_alibaba_qwen_provider(opener, env: dict[str, str]):
    """Ensure Omni ``alibaba`` provider (Qwen/DashScope) when a key is present."""
    return _ensure_alibaba_qwen_provider(http_json, BASE, opener, env)


def ensure_empty_combo(
    opener,
    *,
    name: str,
    description: str,
) -> str:
    """Ensure combo; Qwen-first when Qwen models are active on Omni."""
    n, _ = _ensure_combo_qwen_first(
        http_json,
        BASE,
        opener,
        name=name,
        description=description,
        strategy=COMBO_STRATEGY,
        classify=(name == CLASSIFY_COMBO_NAME),
        reserved_names={COMBO_NAME, CLASSIFY_COMBO_NAME, "qwen-fast"},
        drop_probes=drop_probe_combos,
        member_count=_combo_member_count,
    )
    return n


def ensure_classifier_combo(opener) -> str:
    """Ensure classify combo; Qwen-first when active."""
    return ensure_empty_combo(
        opener,
        name=CLASSIFY_COMBO_NAME,
        description="Classify/intent combo — Qwen first when active (round-robin)",
    )


def ensure_combo_alias(opener) -> str:
    """Ensure chat combo; Qwen-first when active."""
    return ensure_empty_combo(
        opener,
        name=COMBO_NAME,
        description="Stack chat combo — Qwen first when active (round-robin)",
    )


def ensure_qwen_fast_combo(opener) -> str:
    """Dedicated small-Qwen combo (1.5B/1.7B-class), separate from hermes."""
    name, _ = _ensure_combo_qwen_fast(
        http_json,
        BASE,
        opener,
        name=os.environ.get("OMNIROUTER_QWEN_FAST_COMBO", "qwen-fast"),
        strategy=COMBO_STRATEGY,
    )
    return name


def deactivate_non_qwen_llm_providers(opener) -> None:
    """Deactivate LLM providers that do not host current Qwen chat models.

    Keeps search providers and any provider prefix present in Qwen catalog hits
    (alibaba / groq / openrouter / …). Controlled by OMNIROUTER_QWEN_ONLY_PROVIDERS.
    """
    flag = (
        os.environ.get("OMNIROUTER_QWEN_ONLY_PROVIDERS")
        or os.environ.get("OMNI_QWEN_ONLY_PROVIDERS")
        or "1"
    ).strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        print("NOTE: skip deactivate non-Qwen providers (OMNIROUTER_QWEN_ONLY_PROVIDERS off)")
        return
    keep_providers = {
        "alibaba",
        "tavily-search",
        "firecrawl-search",
        "searxng-search",
    }
    try:
        from omnirouter_qwen import is_qwen_chat_model
    except ImportError:
        from omnirouter_qwen import is_qwen_chat_model  # type: ignore
    try:
        _, models_data = http_json(opener, "GET", f"{BASE}/v1/models")
        for row in models_data.get("data") or []:
            if not isinstance(row, dict):
                continue
            mid = row.get("id")
            if isinstance(mid, str) and is_qwen_chat_model(mid):
                keep_providers.add(mid.split("/", 1)[0].lower())
    except Exception as e:  # noqa: BLE001
        print(f"WARN qwen provider keep-scan: {e}")
    _, data = http_json(opener, "GET", f"{BASE}/api/providers")
    for c in data.get("connections") or []:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        prov = str(c.get("provider") or "").lower()
        name = str(c.get("name") or "").lower()
        if prov in keep_providers or name in {"qwen", "dashscope", "alibaba"}:
            continue
        if not c.get("isActive"):
            continue
        try:
            http_json(
                opener,
                "PUT",
                f"{BASE}/api/providers/{c['id']}",
                {"isActive": False},
            )
            print(f"==> deactivate provider id={c['id']} provider={prov!r} name={name!r}")
        except Exception as e:  # noqa: BLE001
            print(f"WARN deactivate {c.get('id')}: {e}")


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

    Hermes does **not** rely on Omni unforced default: Router Worker forces
    ``provider`` per ``OMNIROUTER_SEARCH_PROVIDERS`` (Tavily → Firecrawl → SearXNG).

    OmniRoute quirk (lab): unforced ``POST /v1/search`` still reports
    ``provider=searxng-search`` even when that connection is blocked/deleted;
    connection ``priority`` may not persist on GET after PUT. Keep connections
    active for the forced cascade; judge health via forced Tavily smoke +
    router ``backend=omni:tavily-search``.
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
                "Omni may not persist search priorities — Hermes uses forced provider cascade"
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


def smoke_omni_search(key: str) -> None:
    # Unforced Omni /v1/search often labels searxng-search even when Tavily works;
    # Hermes health is forced-provider (matches Router Worker cascade).
    for label, body_obj in (
        ("unforced", {"query": "Ho Chi Minh weather", "max_results": 2}),
        (
            "forced-tavily",
            {
                "query": "Ho Chi Minh weather",
                "max_results": 2,
                "provider": "tavily-search",
            },
        ),
    ):
        body = json.dumps(body_obj).encode()
        req = urllib.request.Request(
            f"{BASE}/v1/search",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode() or "{}")
            n = len(data.get("results") or [])
            prov = data.get("provider")
            print(f"==> smoke Omni /v1/search ({label}) provider={prov} results={n}")
            if label == "forced-tavily" and prov == "tavily-search" and n > 0:
                print("==> smoke OK: forced tavily-search returns results")
            elif label == "forced-tavily":
                print("WARN smoke: forced tavily-search failed — check Tavily key in Omni")
            elif label == "unforced" and prov == "searxng-search":
                print(
                    "NOTE: Omni unforced default labels searxng-search "
                    "(product quirk); Hermes uses Router Worker forced cascade"
                )
        except urllib.error.HTTPError as e:
            print(f"WARN smoke Omni /v1/search ({label}) HTTP {e.code}: {e.read()[:200]!r}")
        except Exception as e:
            print(f"WARN smoke Omni /v1/search ({label}): {e}")


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

    ensure_alibaba_qwen_provider(opener, env)
    deactivate_non_qwen_llm_providers(opener)
    combo = ensure_combo_alias(opener)
    classify_combo = ensure_classifier_combo(opener)
    qwen_fast = ensure_qwen_fast_combo(opener)
    ensure_combo_round_robin(opener)
    ensure_search_providers(opener)
    set_env_key(ROOT / ".env", "OMNIROUTER_DEFAULT_COMBO", COMBO_NAME)
    set_env_key(ROOT / ".env", "OMNIROUTER_CLASSIFY_COMBO", classify_combo)
    set_env_key(ROOT / ".env", "MODEL_ROUTER_CLASSIFY_MODEL", classify_combo)
    set_env_key(ROOT / ".env", "OMNIROUTER_COMBO_STRATEGY", COMBO_STRATEGY)
    set_env_key(ROOT / ".env", "OMNIROUTER_ENABLE_MEMORY", env.get("OMNIROUTER_ENABLE_MEMORY", "1"))
    # Hermes-facing Router Worker proxies search to Omni by default.
    if env.get("WEB_BACKENDS") in (None, ""):
        set_env_key(ROOT / ".env", "WEB_BACKENDS", "omni")
    enable_omni_memory(opener)

    recreate_model_router()
    time.sleep(3)
    patch_hermes_model_router(key, combo)
    print(
        f"NOTE: skip chat smoke for empty combos {combo!r}/{classify_combo!r} — "
        "Qwen-first when active; re-run smoke after key/provider changes"
    )
    smoke_omni_search(key)
    print(
        f"OK: first-setup omni-router complete "
        f"(chat/classify slim Qwen-only; fast_combo={qwen_fast!r}; "
        f"search via Omni Tavily→Firecrawl→SearXNG)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read()[:300]!r}", file=sys.stderr)
        raise SystemExit(1) from e
