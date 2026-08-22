# Qwen / Alibaba (DashScope) helpers for OmniRouter first-setup.
# Omni provider id is ``alibaba`` (there is no provider id ``qwen``).
from __future__ import annotations

import os
import re
import urllib.error
from typing import Any, Callable

# Matches first-setup-omnirouter.http_json(opener, method, url, body=None) -> (status, data)
HttpJson = Callable[..., tuple[int, dict]]


def qwen_api_key(env: dict[str, str] | None = None) -> str:
    src = env if env is not None else {}
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
        tier = 1
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
    if "instruct" in low:
        penalty -= 1
    if "-vl" in low or "vision" in low:
        penalty += 1
    if any(x in low for x in ("235b", "397b", "2.4t", "qwen3-max")):
        penalty += 1
    return (tier, penalty, low)


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

    ids = sorted(set(ids), key=qwen_sort_key)
    limit = 4 if classify else 8
    out = ids[:limit]
    print(f"==> Qwen chat candidates classify={classify} n={len(out)} sample={out[:5]}")
    return out


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
    qwen_ids = list_qwen_chat_models(http_json, base, opener, classify=classify)
    qwen_active = bool(qwen_ids)

    _, data = http_json(opener, "GET", f"{base}/api/combos")
    combos = data.get("combos") or []
    existing = next((c for c in combos if (c.get("name") or "") == name), None)

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
    elif existing and existing.get("id"):
        n = member_count(existing)
        print(
            f"==> keep combo {name} ({existing['id']}) members={n} "
            "(Qwen inactive — not clearing operator models)"
        )
        try:
            http_json(
                opener,
                "PUT",
                f"{base}/api/combos/{existing['id']}",
                {
                    "name": name,
                    "models": existing.get("models") or [],
                    "strategy": strategy,
                    "description": description,
                },
            )
        except Exception as e:  # noqa: BLE001
            print(f"WARN combo {name} strategy refresh: {e}")
    else:
        print(f"==> create empty combo alias {name} (Qwen inactive)")
        payload = {
            "name": name,
            "models": [],
            "strategy": strategy,
            "description": description,
        }
        created = False
        for attempt in (
            payload,
            {"name": name, "strategy": strategy, "description": description},
        ):
            try:
                status, body = http_json(opener, "POST", f"{base}/api/combos", attempt)
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
