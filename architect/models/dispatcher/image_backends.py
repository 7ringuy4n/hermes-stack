"""Image generation backends for POST /v1/image.

Diffusion order (Media worker active):
  1) omni — OmniRouter /images/generations (combo IMAGE_GEN_COMBO, default image-gen)
  2) n9   — 9Router /images/generations when ENABLE_9ROUTER=1

When Media worker is inactive, IMAGE_GEN_COMBO defaults to hermes (chat combo).
Pillow modes (info-card, text-poster) stay in app.py.

Model id is always the combo for the request type (image-gen / hermes).
Canvas size is optional on the request body (skill declares the HD default).
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx


def _env(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.environ.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def _media_active() -> bool:
    """Media worker on only when ENABLE_MEDIA_FILE or WORKER_MEDIA_FILE is ``active``."""
    for key in ("ENABLE_MEDIA_FILE", "WORKER_MEDIA_FILE"):
        if (os.environ.get(key) or "").strip().lower() == "active":
            return True
    return False


def image_gen_combo() -> str:
    default = "image-gen" if _media_active() else "hermes"
    return _env("IMAGE_GEN_COMBO", default=default)


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
        enabled = (os.environ.get("ENABLE_OMNIROUTER") or "1").strip().lower()
        if enabled in {"0", "false", "no", "off"}:
            return False
        base = _env("OMNIROUTER_BASE_URL", default="http://omni-router:20129/v1")
        key = _env("OMNIROUTER_API_KEY")
        return bool(base and key)
    if n == "n9":
        enabled = (os.environ.get("ENABLE_9ROUTER") or "0").strip().lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return False
        base = _env("N9ROUTER_BASE_URL", "OPENAI_BASE_URL", default="http://9router:20128/v1")
        key = _env("N9ROUTER_API_KEY", "OPENAI_API_KEY")
        return bool(base and key)
    if n == "pillow":
        return True
    return False


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
    """Try router backends in order. Returns (bytes, used_backend, errors)."""
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
    if "pillow" not in order and (os.environ.get("IMAGE_ALLOW_PILLOW") or "0") == "1":
        order.append("pillow")

    if not order:
        raise RuntimeError("no image backends available (configure OmniRouter or 9Router)")

    for b in order:
        if b != "pillow" and not backend_available(b):
            errors.append(f"{b}: skipped (unavailable)")
            continue
        try:
            if b == "omni":
                return gen_omni(prompt, size=size), "omni", errors
            if b == "n9":
                return gen_n9(prompt, size=size), "n9", errors
            if b == "pillow":
                raise RuntimeError("pillow handled by caller")
            errors.append(f"{b}: unknown backend")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{b}: {e}")
            continue
    raise RuntimeError("all image backends failed: " + "; ".join(errors))
