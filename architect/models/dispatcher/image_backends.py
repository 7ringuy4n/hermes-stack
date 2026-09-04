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


def _diffusion_safe_prompt(prompt: str) -> str:
    """Return trimmed diffusion prompt — place aliases and SFW wording belong in classify/skills."""
    return (prompt or "").strip()


def _looks_like_nsfw_censor_placeholder(blob: bytes) -> bool:
    """AI Horde NSFW-block placeholder is a tiny WebP/PNG with burned-in censor text."""
    if not blob:
        return True
    # Real HD scenic WebPs from Flux are typically >100 KiB; censor stubs ~20–35 KiB.
    return len(blob) < 48_000


def _parse_size_wh(size: Optional[str]) -> tuple[int, int]:
    raw = (size or "").strip().lower()
    if not raw or "x" not in raw:
        return 0, 0
    left, _, right = raw.partition("x")
    try:
        return max(0, int(left.strip())), max(0, int(right.strip()))
    except ValueError:
        return 0, 0


def _image_pixel_size(blob: bytes) -> tuple[int, int]:
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(blob)) as im:
        w, h = im.size
        return int(w), int(h)


def _looks_like_low_quality_image(blob: bytes, *, size: Optional[str] = None) -> bool:
    """Reject tiny/censor/low-res diffusion output (blur, dither, upscale stubs)."""
    if _looks_like_nsfw_censor_placeholder(blob):
        return True
    try:
        w, h = _image_pixel_size(blob)
    except Exception:
        return True
    if w < 640 or h < 360:
        return True
    req_w, req_h = _parse_size_wh(size)
    if req_w >= 1280 and w < req_w // 2:
        return True
    if req_h >= 720 and h < req_h // 2:
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
    with httpx.Client(timeout=300.0) as client:
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
    combo = image_gen_combo()
    model = combo
    # Resolve concrete members so Requested Model is populated and combo-level
    # "No images-capable targets" gating is bypassed when members work directly.
    try:
        import json
        import urllib.request

        root = base.rstrip("/")
        url = f"{root}/combos" if root.endswith("/v1") else f"{root}/v1/combos"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode() or "{}")
        rows = data.get("data") or data.get("combos") or []
        entry = next((c for c in rows if isinstance(c, dict) and (c.get("name") or "") == combo), None)
        for row in (entry or {}).get("models") or (entry or {}).get("members") or []:
            mid = ""
            if isinstance(row, str):
                mid = row.strip()
            elif isinstance(row, dict):
                mid = str(row.get("model") or row.get("fullModel") or "").strip()
            if mid and "/" in mid:
                model = mid
                break
    except Exception:
        model = combo
    return _gen_openai_images(
        base=base,
        key=key,
        prompt=prompt,
        model=model,
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
                if _looks_like_low_quality_image(blob, size=size):
                    raise RuntimeError(
                        "low-quality image from combo image-gen — "
                        "check Omni combo members or strengthen SCENE prompt via classify/image-gen"
                    )
                return blob, image_gen_combo(), errors
            if b == "n9":
                blob = gen_n9(safe_prompt, size=size)
                if _looks_like_low_quality_image(blob, size=size):
                    raise RuntimeError(
                        "low-quality image from combo image-gen — "
                        "check combo members or strengthen SCENE prompt via classify/image-gen"
                    )
                return blob, image_gen_combo(), errors
            if b == "pillow":
                raise RuntimeError("pillow handled by caller")
            errors.append(f"{b}: unknown backend")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{b}: {e}")
            continue
    raise RuntimeError("all image backends failed: " + "; ".join(errors))
