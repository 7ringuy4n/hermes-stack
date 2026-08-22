# Qwen / Alibaba (DashScope) helpers for OmniRouter first-setup.
# Omni provider id is ``alibaba`` (there is no provider id ``qwen``).
from __future__ import annotations

import os
import re
import urllib.error
from typing import Any, Callable

# Matches first-setup-omnirouter.http_json(opener, method, url, body=None) -> (status, data)
HttpJson = Callable[..., tuple[int, dict]]


def qwen_enabled(env: dict[str, str] | None = None) -> bool:
    """Qwen is an optional activatable component (ENABLE_QWEN).

    Default off: hermes/classifier stay empty round-robin aliases until the
    operator turns Qwen on and provides a DashScope/Alibaba/Qwen key.
    """
    src = env if env is not None else {}
    raw = (src.get("ENABLE_QWEN") or os.environ.get("ENABLE_QWEN") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def ollama_base_url(env: dict[str, str] | None = None) -> str:
    src = env if env is not None else {}
    return (src.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_BASE_URL") or "").strip().rstrip("/")


def ollama_chat_model(env: dict[str, str] | None = None) -> str:
    """Local Ollama Qwen id for hermes/classifier (e.g. ollama/qwen2.5:7b)."""
    model = (env or {}).get("OLLAMA_MODEL") or os.environ.get("OLLAMA_MODEL") or ""
    model = model.strip()
    if not model or not ollama_base_url(env):
        return ""
    if "/" in model:
        return model if is_qwen_chat_model(model) else ""
    mid = f"ollama/{model}"
    return mid if is_qwen_chat_model(mid) else ""


def ollama_omni_base_url(host_url: str) -> str:
    """Omni runs in Docker — reach host Ollama via host.docker.internal."""
    url = (host_url or "").strip().rstrip("/")
    if not url:
        return ""
    return url.replace("127.0.0.1", "host.docker.internal").replace("localhost", "host.docker.internal")


def ensure_ollama_local_provider(
    http_json: HttpJson,
    base: str,
    opener: Any,
    env: dict[str, str],
) -> dict | None:
    """Register host Ollama (Qwen 2.5 7B-class) when OLLAMA_BASE_URL is set."""
    host_url = ollama_base_url(env)
    if not host_url:
        return None
    omni_url = ollama_omni_base_url(host_url)
    model = ollama_chat_model(env)
    if not model:
        print("NOTE: OLLAMA_BASE_URL set but OLLAMA_MODEL is not a Qwen chat model — skip ollama provider")
        return None
    _, data = http_json(opener, "GET", f"{base}/api/providers")
    conns = data.get("connections") or []
    existing = next(
        (c for c in conns if str(c.get("provider") or "").lower() == "ollama"),
        None,
    )
    payload = {
        "provider": "ollama",
        "name": "local-qwen",
        "isActive": True,
        "priority": 1,
        "apiKey": "ollama",
        "baseUrl": omni_url,
        "providerSpecificData": {"baseUrl": omni_url},
    }
    if existing and existing.get("id"):
        cid = existing["id"]
        print(f"==> update ollama local provider id={cid} base={omni_url}")
        try:
            status, body = http_json(opener, "PUT", f"{base}/api/providers/{cid}", payload)
        except urllib.error.HTTPError as e:
            print(f"WARN update ollama provider HTTP {e.code}: {e.read()[:200]!r}")
            return existing if isinstance(existing, dict) else None
        if status not in (200, 201):
            print(f"WARN update ollama provider rejected: {body}")
            return existing if isinstance(existing, dict) else None
        return body.get("connection") if isinstance(body, dict) else existing

    print(f"==> create ollama local provider base={omni_url} model={model}")
    try:
        status, body = http_json(opener, "POST", f"{base}/api/providers", payload)
    except urllib.error.HTTPError as e:
        print(f"WARN create ollama provider HTTP {e.code}: {e.read()[:200]!r}")
        return None
    if status not in (200, 201):
        print(f"WARN create ollama provider rejected: {body}")
        return None
    conn = body.get("connection") if isinstance(body, dict) else None
    print(f"==> ollama local provider created id={(conn or {}).get('id')}")
    return conn if isinstance(conn, dict) else None


def qwen_api_key(env: dict[str, str] | None = None) -> str:
    src = env if env is not None else {}
    if not qwen_enabled(src):
        return ""
    for k in (
        "QWEN_API_KEY",
        "ALIBABA_API_KEY",
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_API_KEY_INTL",
    ):
        v = (src.get(k) or os.environ.get(k) or "").strip()
        if v:
            return v
    return ""


def provider_id_for_model(model_id: str) -> str:
    prefix = (model_id or "").split("/", 1)[0].strip().lower()
    return {
        "ollamacloud": "ollama-cloud",
        "cf": "cloudflare-ai",
        "oc": "opencode",
    }.get(prefix, prefix)


def is_qwen_chat_model(model_id: str) -> bool:
    mid = (model_id or "").strip()
    low = mid.lower()
    if not mid:
        return False
    if low.startswith("alibaba/"):
        pass
    elif "qwen" not in low:
        return False
    bad = (
        "embed",
        "whisper",
        "tts",
        "orpheus",
        "rerank",
        "image-",
        "flux",
        "stable-diffusion",
    )
    return not any(b in low for b in bad)


def qwen_sort_key(model_id: str) -> tuple:
    """Prefer chat/instruct Qwen that return visible text (not think-only).

    Qwen3.x often spends the whole max_tokens budget inside ``<think>`` and
    finishes with ``finish_reason=length`` and empty user-visible content —
    Zalo then waits on compound delivery until the 150s queue turn timeout
    and the user sees no reply.
    """
    low = model_id.lower()
    if low.startswith("alibaba/"):
        tier = 0
    elif low.startswith("groq/") and "qwen" in low:
        tier = 1  # prefer Groq Qwen when OpenRouter is credit-blocked (402)
    elif low.startswith("openrouter/") and "qwen" in low:
        tier = 2
    else:
        tier = 3
    penalty = 0
    if "thinking" in low or "reason" in low:
        penalty += 5
    # Qwen3.x chat ids (qwen3.6, qwen3-…) default to hidden reasoning tokens.
    if re.search(r"qwen3(?:[.\-]|\b)", low) or "/qwen3" in low:
        penalty += 6
    if any(x in low for x in ("qwen2.5", "qwen-2.5", "qwen-plus", "qwen-turbo", "qwen-max")):
        penalty -= 3
    if re.search(r"(?:^|[./\-:])7b(?:$|[./\-:])", low) and "72b" not in low and "32b" not in low:
        penalty -= 4
    if "instruct" in low:
        penalty -= 1
    if "-vl" in low or "vision" in low:
        penalty += 1
    if any(x in low for x in ("235b", "397b", "2.4t", "qwen3-max")):
        penalty += 1
    # Penalty first so Groq Qwen3 (tier=1, penalty=6) loses to OpenRouter
    # Qwen2.5 (tier=2, penalty=-3). Otherwise think-only models stay first.
    return (penalty, tier, low)


def ensure_alibaba_qwen_provider(
    http_json: HttpJson,
    base: str,
    opener: Any,
    env: dict[str, str],
) -> dict | None:
    key = qwen_api_key(env)
    _, data = http_json(opener, "GET", f"{base}/api/providers")
    conns = data.get("connections") or []
    existing = next(
        (
            c
            for c in conns
            if str(c.get("provider") or "").lower() == "alibaba"
            and str(c.get("name") or "").lower()
            in {"qwen", "alibaba", "dashscope", "main"}
        ),
        None,
    )
    if not existing:
        existing = next(
            (c for c in conns if str(c.get("provider") or "").lower() == "alibaba"),
            None,
        )

    if not key:
        if existing and existing.get("isActive"):
            print(
                f"==> keep active alibaba/Qwen provider id={existing.get('id')} "
                f"name={existing.get('name')!r}"
            )
            return existing if isinstance(existing, dict) else None
        print(
            "NOTE: no QWEN_API_KEY / ALIBABA_API_KEY / DASHSCOPE_API_KEY — "
            "skip creating alibaba provider; will use Qwen via Groq/OpenRouter if active"
        )
        return existing if isinstance(existing, dict) else None

    payload = {
        "provider": "alibaba",
        "authType": "apikey",
        "name": "qwen",
        "apiKey": key,
        "isActive": True,
        "priority": 1,
    }
    if existing and existing.get("id"):
        cid = existing["id"]
        print(f"==> update alibaba/Qwen provider id={cid}")
        try:
            status, body = http_json(
                opener, "PUT", f"{base}/api/providers/{cid}", payload
            )
        except urllib.error.HTTPError as e:
            print(f"WARN update alibaba provider HTTP {e.code}: {e.read()[:200]!r}")
            return existing
        if status not in (200, 201):
            print(f"WARN update alibaba provider rejected: {body}")
            return existing
        return body.get("connection") if isinstance(body, dict) else existing

    print("==> create alibaba/Qwen provider connection name=qwen")
    try:
        status, body = http_json(opener, "POST", f"{base}/api/providers", payload)
    except urllib.error.HTTPError as e:
        print(f"WARN create alibaba provider HTTP {e.code}: {e.read()[:200]!r}")
        return None
    if status not in (200, 201):
        print(f"WARN create alibaba provider rejected: {body}")
        return None
    conn = body.get("connection") if isinstance(body, dict) else None
    print(f"==> alibaba/Qwen provider created id={(conn or {}).get('id')}")
    if conn and conn.get("id"):
        try:
            http_json(opener, "POST", f"{base}/api/providers/{conn['id']}/test")
        except Exception as e:  # noqa: BLE001
            print(f"WARN alibaba provider test: {e}")
    return conn if isinstance(conn, dict) else None


def list_qwen_chat_models(
    http_json: HttpJson,
    base: str,
    opener: Any,
    *,
    classify: bool = False,
) -> list[str]:
    ids: list[str] = []
    try:
        _, data = http_json(opener, "GET", f"{base}/v1/models")
        for row in data.get("data") or []:
            if not isinstance(row, dict):
                continue
            mid = row.get("id")
            if isinstance(mid, str) and is_qwen_chat_model(mid):
                ids.append(mid.strip())
    except Exception as e:  # noqa: BLE001
        print(f"WARN list Qwen models via /v1/models: {e}")

    try:
        _, pdata = http_json(opener, "GET", f"{base}/api/providers")
        active = {
            str(c.get("provider") or "").lower()
            for c in (pdata.get("connections") or [])
            if c.get("isActive")
        }
        aliases = set(active)
        if "ollama-cloud" in active:
            aliases.add("ollamacloud")
        if "cloudflare-ai" in active:
            aliases.add("cf")
        if "opencode" in active:
            aliases.add("oc")
        filtered = [
            mid
            for mid in ids
            if mid.split("/", 1)[0].lower() in aliases
            or mid.split("/", 1)[0].lower() in active
        ]
        if filtered:
            ids = filtered
        else:
            print("WARN no Qwen models matched active providers — using catalog hits")
    except Exception as e:  # noqa: BLE001
        print(f"WARN filter Qwen by active providers: {e}")

    local = ollama_chat_model()
    if local and local not in ids:
        ids.append(local)

    ids = sorted(set(ids), key=qwen_sort_key)
    limit = 1 if classify else 2  # slim: 1 classifier + <=2 hermes Qwen chat models
    out = ids[:limit]
    print(f"==> Qwen chat candidates classify={classify} n={len(out)} sample={out[:5]}")
    return out



def is_qwen_fast_small(model_id: str) -> bool:
    """Tiny Qwen (~0.5B–3B / 1.5B / 1.7B) for a dedicated low-latency combo."""
    low = (model_id or "").lower()
    if not is_qwen_chat_model(low):
        return False
    if any(x in low for x in ("thinking", "reason", "-vl", "vision")):
        return False
    return bool(
        re.search(r"(?:^|[./\-])(?:0\.5b|1\.5b|1\.7b|1b|1\.8b|3b)(?:$|[./\-])", low)
        or "1.5b" in low
        or "1.7b" in low
    )


def list_qwen_fast_models(
    http_json: HttpJson,
    base: str,
    opener: Any,
) -> list[str]:
    """Best tiny Qwen ids from the full catalog (not the slim hermes limit)."""
    ids: list[str] = []
    try:
        _, data = http_json(opener, "GET", f"{base}/v1/models")
        for row in data.get("data") or []:
            if not isinstance(row, dict):
                continue
            mid = row.get("id")
            if isinstance(mid, str) and is_qwen_fast_small(mid):
                ids.append(mid.strip())
    except Exception as e:  # noqa: BLE001
        print(f"WARN list Qwen-fast models: {e}")
    ids = sorted(set(ids), key=qwen_sort_key)
    out = ids[:2]
    print(f"==> Qwen-fast candidates n={len(out)} sample={out}")
    return out


def ensure_combo_qwen_fast(
    http_json: HttpJson,
    base: str,
    opener: Any,
    *,
    name: str = "qwen-fast",
    strategy: str = "round-robin",
) -> tuple[str, bool]:
    """Dedicated combo for small Qwen (1.5B/1.7B-class) — separate from hermes."""
    if not qwen_enabled():
        print(f"NOTE: skip combo {name} (ENABLE_QWEN off)")
        return name, False
    fast_ids = list_qwen_fast_models(http_json, base, opener)
    _, data = http_json(opener, "GET", f"{base}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == name), None)
    if not fast_ids:
        print(f"NOTE: no tiny Qwen for combo {name} — leave empty/absent")
        return name, False
    models = [combo_model_entry(name, i + 1, mid) for i, mid in enumerate(fast_ids)]
    payload = {
        "name": name,
        "models": models,
        "strategy": strategy,
        "description": "Dedicated small Qwen (~1.5B/1.7B) for low-latency turns",
    }
    action = "update" if existing and existing.get("id") else "create"
    print(f"==> {action} combo {name} n={len(models)} ids={fast_ids}")
    if existing and existing.get("id"):
        status, body = http_json(
            opener, "PUT", f"{base}/api/combos/{existing['id']}", payload
        )
    else:
        status, body = http_json(opener, "POST", f"{base}/api/combos", payload)
    if status not in (200, 201):
        print(f"WARN combo {name} {action} failed: {body}")
        return name, False
    return name, True



def combo_model_entry(combo_name: str, index: int, model_id: str) -> dict:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", model_id).strip("-").lower()[:60]
    return {
        "id": f"{combo_name}-model-{index}-{slug}",
        "kind": "model",
        "model": model_id,
        "providerId": provider_id_for_model(model_id),
        "weight": 0,
    }


def existing_model_ids(combo: dict | None, reserved: set[str]) -> list[str]:
    if not combo:
        return []
    out: list[str] = []
    for m in combo.get("models") or combo.get("members") or []:
        if isinstance(m, str) and m.strip():
            mid = m.strip()
            if mid not in reserved and ("/" in mid or mid.startswith("oc/")):
                out.append(mid)
        elif isinstance(m, dict):
            mid = m.get("model") or m.get("id") or m.get("name")
            if (
                isinstance(mid, str)
                and mid.strip()
                and m.get("kind", "model") == "model"
                and mid.strip() not in reserved
                and ("/" in mid or mid.startswith("oc/"))
            ):
                out.append(mid.strip())
    return out


def ensure_combo_qwen_first(
    http_json: HttpJson,
    base: str,
    opener: Any,
    *,
    name: str,
    description: str,
    strategy: str,
    classify: bool,
    reserved_names: set[str],
    drop_probes: Callable[[Any], None],
    member_count: Callable[[dict], int],
) -> tuple[str, bool]:
    drop_probes(opener)
    qwen_ids: list[str] = []
    if qwen_enabled():
        qwen_ids = list_qwen_chat_models(http_json, base, opener, classify=classify)
    elif not qwen_enabled():
        print(f"NOTE: ENABLE_QWEN off — combo {name} will stay empty round-robin")
    # Active when ENABLE_QWEN=1 and Omni catalog has Qwen on active providers
    # (OpenRouter/Groq/Ollama/alibaba). DashScope key is optional — only needed
    # for the alibaba provider connection, not to populate hermes/classifier.
    qwen_active = bool(qwen_ids) and qwen_enabled()

    _, data = http_json(opener, "GET", f"{base}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == name), None)

    # Default product posture: empty hermes/classifier with round-robin until
    # ENABLE_QWEN=1 and Omni catalog yields Qwen chat models on active providers.
    if qwen_active:
        # When Qwen is active, use Qwen members only. Keeping prior ollamacloud /
        # other RR members lets sticky round-robin land on empty_choices / slow
        # failures and burn the Zalo queue turn budget (no user reply).
        uniq: list[str] = []
        seen: set[str] = set()
        for m in qwen_ids:
            if m in seen:
                continue
            seen.add(m)
            uniq.append(m)
        models = [combo_model_entry(name, i + 1, mid) for i, mid in enumerate(uniq)]
        payload = {
            "name": name,
            "models": models,
            "strategy": strategy,
            "description": description,
        }
        action = "update" if existing and existing.get("id") else "create"
        print(f"==> {action} combo {name} Qwen-only n={len(models)} first={uniq[:3]}")
        if existing and existing.get("id"):
            status, body = http_json(
                opener, "PUT", f"{base}/api/combos/{existing['id']}", payload
            )
        else:
            status, body = http_json(opener, "POST", f"{base}/api/combos", payload)
        if status not in (200, 201):
            raise SystemExit(f"combo {name} {action} failed: {body}")
    else:
        # Force empty members (round-robin) so first-setup never leaves stale
        # OpenCode/ollamacloud models in hermes/classifier by default.
        _ = member_count  # signature compatibility
        payload = {
            "name": name,
            "models": [],
            "strategy": strategy,
            "description": description,
        }
        if existing and existing.get("id"):
            print(
                f"==> clear combo {name} ({existing['id']}) to empty "
                f"round-robin (Qwen inactive / ENABLE_QWEN off)"
            )
            status, body = http_json(
                opener, "PUT", f"{base}/api/combos/{existing['id']}", payload
            )
            if status not in (200, 201):
                print(f"WARN clear {name} failed: {body}")
        else:
            print(f"==> create empty combo alias {name} (Qwen inactive)")
            created = False
            for attempt in (
                payload,
                {"name": name, "strategy": strategy, "description": description},
            ):
                try:
                    status, body = http_json(
                        opener, "POST", f"{base}/api/combos", attempt
                    )
                except urllib.error.HTTPError as e:
                    print(f"WARN create {name} HTTP {e.code}: {e.read()[:200]!r}")
                    continue
                if status in (200, 201):
                    created = True
                    break
                print(f"WARN create {name} rejected: {body}")
            if not created:
                raise SystemExit(f"could not create combo alias {name!r}")

    try:
        http_json(
            opener,
            "PATCH",
            f"{base}/api/settings",
            {"comboStrategies": {name: {"fallbackStrategy": strategy}}},
        )
    except Exception as e:  # noqa: BLE001
        print(f"WARN {name} comboStrategies patch: {e}")
    return name, qwen_active
