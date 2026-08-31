"""Image generation backends (legacy helper; scenic diffusion is Omni-direct).

Diffusion via OmniRouter /images/generations always uses combo IMAGE_GEN_COMBO
(default ``image-gen``) whether Media worker is active or inactive — never the
chat combo ``hermes`` for still images.

Pillow modes (text-poster only) stay in app.py. Canvas size is optional on the
request body (skill declares the HD default).

SFW / anti-censor wording lives in classify + image-gen skills — this module does
not invent retry prompt templates.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from env_flags import env_active, env_inactive


def _env(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.environ.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def image_gen_combo() -> str:
    """Still-image combo name — always image-gen unless IMAGE_GEN_COMBO overrides."""
    return _env("IMAGE_GEN_COMBO", default="image-gen")


def image_backends() -> list[str]:
    out: list[str] = []
    if backend_available("omni"):
        out.append("omni")
    if backend_available("n9"):
        out.append("n9")
    return out


def backend_available(name: str) -> bool:
    n = (name or "").strip().lower()
    if n == "omni":
        if env_inactive("ENABLE_OMNIROUTER", default="active"):
            return False
        base = _env("OMNIROUTER_BASE_URL", default="http://omni-router:20129/v1")
        key = _env("OMNIROUTER_API_KEY")
        return bool(base and key)
    if n == "n9":
        if not env_active("ENABLE_9ROUTER", default="inactive"):
            return False
        base = _env("N9ROUTER_BASE_URL", "OPENAI_BASE_URL", default="http://9router:20128/v1")
        key = _env("N9ROUTER_API_KEY", "OPENAI_API_KEY")
        return bool(base and key)
    if n == "pillow":
        return True
    return False


def _replace_ci(text: str, old: str, new: str) -> str:
    """Case-insensitive substring replace without regex."""
    if not text or not old:
        return text
    lower = text.lower()
    needle = old.lower()
    out: list[str] = []
    i = 0
    while True:
        j = lower.find(needle, i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        out.append(new)
        i = j + len(old)
    return "".join(out)


def _diffusion_safe_prompt(prompt: str) -> str:
    """Map known safety-filter false-positive place aliases to official English names.

    AI Horde workers censor prompts containing colloquial "Saigon" even for SFW cityscapes.
    Classify/image-gen should already emit Ho Chi Minh City; this is a durable host guard.
    """
    p = (prompt or "").strip()
    if not p:
        return p
    for old, new in (
        ("sài gòn", "Ho Chi Minh City"),
        ("sai gòn", "Ho Chi Minh City"),
        ("sai gon", "Ho Chi Minh City"),
        ("saigon", "Ho Chi Minh City"),
    ):
        p = _replace_ci(p, old, new)
    return p


def _looks_like_nsfw_censor_placeholder(blob: bytes) -> bool:
    """AI Horde NSFW-block placeholder is a tiny WebP/PNG with burned-in censor text."""
    if not blob:
        return True
    # Real HD scenic WebPs from Flux are typically >100 KiB; censor stubs ~20–35 KiB.
    return len(blob) < 48_000


def _gen_openai_images(
    *,
    base: str,
    key: str,
    prompt: str,
    model: str,
    size: Optional[str] = None,
) -> bytes:
    endpoint = base if base.endswith("/images/generations") else f"{base.rstrip('/')}/images/generations"
    headers = {"content-type": "application/json", "authorization": f"Bearer {key}"}
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "n": 1}
    if size and str(size).strip():
        payload["size"] = str(size).strip()
    with httpx.Client(timeout=180.0) as client:
        r = client.post(endpoint, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data") or data.get("images") or []
            if isinstance(items, dict):
                items = [items]
        else:
            items = []
        if not items:
            raise RuntimeError(f"no image data: {str(data)[:300]}")
        item = items[0]
        if not isinstance(item, dict):
            raise RuntimeError(f"bad image item: {str(item)[:200]}")
        if item.get("b64_json"):
            import base64

            return base64.b64decode(item["b64_json"])
        url = item.get("url")
        if not url:
            raise RuntimeError(f"no url/b64: {item}")
        img = client.get(url)
        img.raise_for_status()
        return img.content


def gen_omni(prompt: str, *, size: Optional[str] = None) -> bytes:
    base = _env("OMNIROUTER_BASE_URL", default="http://omni-router:20129/v1")
    key = _env("OMNIROUTER_API_KEY")
    if not key:
        raise RuntimeError("OMNIROUTER_API_KEY missing")
    return _gen_openai_images(
        base=base,
        key=key,
        prompt=prompt,
        model=image_gen_combo(),
        size=size,
    )


def gen_n9(prompt: str, *, size: Optional[str] = None) -> bytes:
    base = _env("N9ROUTER_BASE_URL", "OPENAI_BASE_URL", default="http://9router:20128/v1")
    key = _env("N9ROUTER_API_KEY", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("N9ROUTER_API_KEY missing")
    return _gen_openai_images(
        base=base,
        key=key,
        prompt=prompt,
        model=image_gen_combo(),
        size=size,
    )


def generate_image_bytes(
    prompt: str,
    provider: Optional[str] = None,
    *,
    size: Optional[str] = None,
) -> tuple[bytes, str, list[str]]:
    """Try router backends in order. Returns (bytes, used_backend, errors).

    Does not invent SFW retry templates — classify/image-gen skills own prompt hardening.
    """
    errors: list[str] = []
    order: list[str] = []
    if provider:
        p = provider.strip().lower()
        if p in {"9router", "n9router"}:
            p = "n9"
        if p in {"omni", "n9"}:
            order.append(p)
    for b in image_backends():
        if b not in order:
            order.append(b)
    if "pillow" not in order and env_active("IMAGE_ALLOW_PILLOW", default="inactive"):
        order.append("pillow")

    if not order:
        raise RuntimeError("no image backends available (configure OmniRouter or 9Router)")

    safe_prompt = _diffusion_safe_prompt(prompt)
    if safe_prompt != (prompt or "").strip():
        errors.append("prompt: mapped colloquial place alias for diffusion safety filters")

    for b in order:
        if b != "pillow" and not backend_available(b):
            errors.append(f"{b}: skipped (unavailable)")
            continue
        try:
            if b == "omni":
                blob = gen_omni(safe_prompt, size=size)
                if _looks_like_nsfw_censor_placeholder(blob):
                    raise RuntimeError(
                        "nsfw censor placeholder from image provider — "
                        "strengthen SCENE prompt (SFW, official place names) via classify/image-gen"
                    )
                return blob, "omni", errors
            if b == "n9":
                blob = gen_n9(safe_prompt, size=size)
                if _looks_like_nsfw_censor_placeholder(blob):
                    raise RuntimeError(
                        "nsfw censor placeholder from image provider — "
                        "strengthen SCENE prompt (SFW, official place names) via classify/image-gen"
                    )
                return blob, "n9", errors
            if b == "pillow":
                raise RuntimeError("pillow handled by caller")
            errors.append(f"{b}: unknown backend")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{b}: {e}")
            continue
    raise RuntimeError("all image backends failed: " + "; ".join(errors))
