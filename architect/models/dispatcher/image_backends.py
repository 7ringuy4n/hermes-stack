"""Image generation backends for POST /v1/image.

Diffusion order (Media worker):
  1) omni — OmniRouter OpenAI-compatible /images/generations (combo ``image-gen``)
  2) n9   — 9Router OpenAI-compatible /images/generations when ENABLE_9ROUTER=1

Pillow modes (info-card, text-poster) stay in app.py — not diffusion.
ComfyUI and paid vendor image keys are removed.
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


def image_gen_combo() -> str:
    return _env("IMAGE_GEN_COMBO", "IMAGE_OMNI_MODEL", default="image-gen")


def image_gen_size() -> str:
    return _env("IMAGE_GEN_SIZE", "IMAGE_OMNI_SIZE", default="1024x1024")


def _split_backends() -> list[str]:
    """Resolved provider order. Empty IMAGE_BACKENDS legacy → auto from flags."""
    raw = os.environ.get("IMAGE_BACKENDS")
    if raw is not None and str(raw).strip():
        out: list[str] = []
        for b in raw.split(","):
            n = b.strip().lower()
            # Legacy aliases → router backends
            if n in {"comfy-cpu", "comfy_cpu", "cpu", "comfy-gpu", "comfy_gpu", "gpu"}:
                continue
            if n in {"paid1", "paid2", "llm", "vendor", "omni"}:
                n = "omni"
            if n in {"n9", "9router", "n9router"}:
                n = "n9"
            if n and n not in out:
                out.append(n)
        if out:
            return out
    out = []
    if backend_available("omni"):
        out.append("omni")
    if backend_available("n9"):
        out.append("n9")
    return out


def image_backends() -> list[str]:
    return _split_backends()


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


def _gen_openai_images(*, base: str, key: str, prompt: str, model: str, size: str) -> bytes:
    endpoint = base if base.endswith("/images/generations") else f"{base.rstrip('/')}/images/generations"
    headers = {"content-type": "application/json", "authorization": f"Bearer {key}"}
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "n": 1, "size": size}
    with httpx.Client(timeout=180.0) as client:
        r = client.post(endpoint, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        items = data.get("data") or []
        if not items:
            raise RuntimeError(f"no image data: {str(data)[:300]}")
        item = items[0]
        if item.get("b64_json"):
            import base64

            return base64.b64decode(item["b64_json"])
        url = item.get("url")
        if not url:
            raise RuntimeError(f"no url/b64: {item}")
        img = client.get(url)
        img.raise_for_status()
        return img.content


def gen_omni(prompt: str) -> bytes:
    base = _env("OMNIROUTER_BASE_URL", default="http://omni-router:20129/v1")
    key = _env("OMNIROUTER_API_KEY")
    if not key:
        raise RuntimeError("OMNIROUTER_API_KEY missing")
    return _gen_openai_images(
        base=base,
        key=key,
        prompt=prompt,
        model=image_gen_combo(),
        size=image_gen_size(),
    )


def gen_n9(prompt: str) -> bytes:
    base = _env("N9ROUTER_BASE_URL", "OPENAI_BASE_URL", default="http://9router:20128/v1")
    key = _env("N9ROUTER_API_KEY", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("N9ROUTER_API_KEY missing")
    return _gen_openai_images(
        base=base,
        key=key,
        prompt=prompt,
        model=image_gen_combo(),
        size=image_gen_size(),
    )


def generate_image_bytes(prompt: str, provider: Optional[str] = None) -> tuple[bytes, str, list[str]]:
    """Try router backends in order. Returns (bytes, used_backend, errors)."""
    errors: list[str] = []
    order: list[str] = []
    if provider:
        p = provider.strip().lower()
        if p in {"comfy-cpu", "comfy-gpu", "cpu", "gpu", "comfy"}:
            p = "omni"
        if p in {"9router", "n9router"}:
            p = "n9"
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
                return gen_omni(prompt), "omni", errors
            if b == "n9":
                return gen_n9(prompt), "n9", errors
            if b == "pillow":
                raise RuntimeError("pillow handled by caller")
            errors.append(f"{b}: unknown backend")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{b}: {e}")
            continue
    raise RuntimeError("all image backends failed: " + "; ".join(errors))
