"""Image generation backends for POST /v1/image.

Fallback order (Medium+ default):
  1) llm     — LLM image APIs (OpenAI · Gemini · DeepSeek · custom OpenAI-compat)
  2) vendor  — specialty hosts (fal · pollinations · fluxai · openai · http)
  3) comfy-cpu — self-hosted ComfyUI, no VGA (SDXL or SD 1.5)
  4) comfy-gpu — self-hosted ComfyUI + VGA (FLUX.2 [klein] 4B)

Legacy aliases: paid1→llm, paid2→vendor (IMAGE_PAID1_* / IMAGE_PAID2_* still read).

Low: IMAGE_BACKENDS empty → callers get 503.
Missing keys / GPU off → that step is skipped.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

ROOT = Path(__file__).resolve().parent
WORKFLOW_DIR = Path(os.environ.get("COMFYUI_WORKFLOW_DIR") or (ROOT / "comfy_workflows"))

# Backend name aliases (old → new)
_BACKEND_ALIASES = {
    "paid1": "llm",
    "paid2": "vendor",
}

# LLM provider presets (IMAGE_LLM_PROVIDER)
_LLM_PRESETS: dict[str, dict[str, str]] = {
    "openai": {
        "base": "https://api.openai.com/v1",
        "model": "dall-e-3",
    },
    "gemini": {
        # OpenAI-compatible Gemini endpoint (Imagen / native image models via compat layer)
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "imagen-3.0-generate-002",
    },
    "google": {  # alias → gemini
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "imagen-3.0-generate-002",
    },
    "deepseek": {
        "base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",  # override IMAGE_LLM_MODEL when DeepSeek ships image models
    },
}


def _norm_backend(name: str) -> str:
    n = name.strip().lower()
    return _BACKEND_ALIASES.get(n, n)


def _split_backends() -> list[str]:
    raw = os.environ.get("IMAGE_BACKENDS")
    if raw is None:
        return ["llm", "vendor", "comfy-cpu", "comfy-gpu"]
    out: list[str] = []
    for b in raw.split(","):
        b = _norm_backend(b)
        if b and b not in out:
            out.append(b)
    return out


def image_backends() -> list[str]:
    return _split_backends()


def _env(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.environ.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def _llm_provider() -> str:
    p = _env("IMAGE_LLM_PROVIDER", "IMAGE_PAID1_PROVIDER", default="openai").lower()
    aliases = {
        "gpt": "openai",
        "dall-e": "openai",
        "dalle": "openai",
        "chatgpt": "openai",
        "google": "gemini",
        "imagen": "gemini",
        "ds": "deepseek",
        "custom": "custom",
        "compat": "custom",
        "openai-compat": "custom",
    }
    return aliases.get(p, p)


def _llm_key() -> str:
    return _env(
        "IMAGE_LLM_API_KEY",
        "IMAGE_PAID1_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY",
        "N9ROUTER_API_KEY",
    )


def _llm_base_and_model() -> tuple[str, str]:
    prov = _llm_provider()
    preset = _LLM_PRESETS.get(prov, {})
    base = _env(
        "IMAGE_LLM_BASE_URL",
        "IMAGE_PAID1_BASE_URL",
        "OPENAI_BASE_URL",
        default=preset.get("base") or "https://api.openai.com/v1",
    ).rstrip("/")
    model = _env(
        "IMAGE_LLM_MODEL",
        "IMAGE_PAID1_MODEL",
        "IMAGE_MODEL",
        default=preset.get("model") or "dall-e-3",
    )
    if prov == "custom" and not _env("IMAGE_LLM_BASE_URL", "IMAGE_PAID1_BASE_URL"):
        raise RuntimeError("IMAGE_LLM_BASE_URL required when IMAGE_LLM_PROVIDER=custom")
    return base, model


def _vendor_provider() -> str:
    p = _env("IMAGE_VENDOR_PROVIDER", "IMAGE_PAID2_PROVIDER", default="fal").lower()
    aliases = {
        "fal.ai": "fal",
        "fal-ai": "fal",
        "pollination": "pollinations",
        "pollinations.ai": "pollinations",
        "flux": "fluxai",
        "flux-ai": "fluxai",
        "flux image generator": "fluxai",
        "fluximage": "fluxai",
        "fluxxai": "fluxai",
        "fluxx": "fluxai",
        "custom": "http",
        "url": "http",
        "openai-images": "openai",
        "dalle": "openai",
    }
    return aliases.get(p, p)


def _vendor_key() -> str:
    return _env(
        "IMAGE_VENDOR_API_KEY",
        "IMAGE_PAID2_API_KEY",
        "FAL_KEY",
        "FAL_API_KEY",
        "FLUXAI_API_KEY",
        "POLLINATIONS_API_KEY",
    )


def _has_gpu() -> bool:
    v = (os.environ.get("COMFYUI_HAS_GPU") or "0").strip().lower()
    return v in {"1", "true", "yes", "on"}


def backend_available(name: str) -> bool:
    n = _norm_backend(name)
    if n == "llm":
        return bool(_llm_key())
    if n == "vendor":
        prov = _vendor_provider()
        if prov == "pollinations":
            return True
        if prov == "http":
            return bool(_env("IMAGE_VENDOR_URL", "IMAGE_PAID2_URL"))
        if prov == "openai":
            return bool(_vendor_key() or _llm_key())
        if prov == "fluxai":
            return bool(_vendor_key()) and bool(
                _env("IMAGE_VENDOR_URL", "IMAGE_PAID2_URL", "FLUXAI_URL")
            )
        return bool(_vendor_key())
    if n == "fal":
        return bool(_vendor_key())
    if n == "pollinations":
        return True
    if n in {"fluxai", "flux"}:
        return bool(_vendor_key()) and bool(
            _env("IMAGE_VENDOR_URL", "IMAGE_PAID2_URL", "FLUXAI_URL")
        )
    if n in {"comfy-cpu", "comfy_cpu", "cpu"}:
        return bool(_env("COMFYUI_CPU_URL", "COMFYUI_URL"))
    if n in {"comfy-gpu", "comfy_gpu", "gpu"}:
        if not _has_gpu():
            return False
        return bool(_env("COMFYUI_GPU_URL", "COMFYUI_URL"))
    if n == "pillow":
        return True
    return False


def gen_llm(prompt: str) -> bytes:
    """LLM images via OpenAI-compatible /images/generations (OpenAI · Gemini · DeepSeek · custom)."""
    key = _llm_key()
    if not key:
        raise RuntimeError("IMAGE_LLM_API_KEY missing (or OPENAI_API_KEY / GEMINI_API_KEY / DEEPSEEK_API_KEY)")
    base, model = _llm_base_and_model()
    size = _env("IMAGE_LLM_SIZE", "IMAGE_PAID1_SIZE", default="1920x1080")
    prov = _llm_provider()
    headers = {"content-type": "application/json", "authorization": f"Bearer {key}"}
    # Gemini often also accepts x-goog-api-key
    if prov == "gemini":
        headers["x-goog-api-key"] = key
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "n": 1, "size": size}
    with httpx.Client(timeout=180.0) as client:
        r = client.post(f"{base}/images/generations", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        items = data.get("data") or []
        if not items:
            raise RuntimeError(f"llm({prov}): no image data: {data}")
        item = items[0]
        if item.get("b64_json"):
            import base64

            return base64.b64decode(item["b64_json"])
        url = item.get("url")
        if not url:
            raise RuntimeError(f"llm({prov}): no url/b64: {item}")
        img = client.get(url)
        img.raise_for_status()
        return img.content


# Back-compat name
gen_paid1 = gen_llm


def gen_pollinations(prompt: str) -> bytes:
    """Pollinations (public; optional POLLINATIONS_API_KEY / IMAGE_VENDOR_API_KEY)."""
    from urllib.parse import quote as q

    base = _env("POLLINATIONS_URL", default="https://image.pollinations.ai/prompt").rstrip("/")
    url = f"{base}/{q(prompt)}?width=768&height=512&nologo=true"
    key = _env("POLLINATIONS_API_KEY", "IMAGE_VENDOR_API_KEY", "IMAGE_PAID2_API_KEY")
    headers = {}
    if key:
        headers["authorization"] = f"Bearer {key}"
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        r = client.get(url, headers=headers or None)
        r.raise_for_status()
        if "image" not in r.headers.get("content-type", "") and len(r.content) < 1000:
            raise RuntimeError(f"pollinations bad ctype={r.headers.get('content-type')}")
        return r.content


def gen_fal(prompt: str) -> bytes:
    key = _vendor_key()
    if not key:
        raise RuntimeError("IMAGE_VENDOR_API_KEY / FAL_KEY missing")
    model = _env("IMAGE_VENDOR_MODEL", "IMAGE_PAID2_MODEL", default="fal-ai/flux/schnell")
    url = _env("IMAGE_VENDOR_URL", "IMAGE_PAID2_URL", default=f"https://fal.run/{model}")
    headers = {"authorization": f"Key {key}", "content-type": "application/json"}
    payload = {"prompt": prompt, "image_size": "landscape_4_3", "num_images": 1}
    with httpx.Client(timeout=180.0) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        images = data.get("images") or []
        if not images and isinstance(data.get("image"), dict):
            images = [data["image"]]
        if not images:
            raise RuntimeError(f"fal: no images: {str(data)[:300]}")
        img_url = images[0].get("url") if isinstance(images[0], dict) else None
        if not img_url:
            raise RuntimeError(f"fal: missing image url: {images[0]}")
        img = client.get(img_url)
        img.raise_for_status()
        return img.content


def gen_fluxai(prompt: str) -> bytes:
    """FluxAI / Flux Image Generator — IMAGE_VENDOR_URL + API key."""
    key = _vendor_key()
    if not key:
        raise RuntimeError("IMAGE_VENDOR_API_KEY / FLUXAI_API_KEY missing")
    url = _env("IMAGE_VENDOR_URL", "IMAGE_PAID2_URL", "FLUXAI_URL")
    if not url:
        raise RuntimeError(
            "IMAGE_VENDOR_URL required for IMAGE_VENDOR_PROVIDER=fluxai "
            "(set your FluxAI / Flux Image Generator endpoint)"
        )
    headers = {
        "authorization": f"Bearer {key}",
        "content-type": "application/json",
        "x-api-key": key,
    }
    model = _env("IMAGE_VENDOR_MODEL", "IMAGE_PAID2_MODEL")
    payload: dict[str, Any] = {"prompt": prompt}
    if model:
        payload["model"] = model
    with httpx.Client(timeout=180.0) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "image/" in ctype:
            return r.content
        data = r.json()
        img_url = (
            data.get("url")
            or data.get("image_url")
            or data.get("output")
            or (data.get("data") or {}).get("url")
        )
        images = data.get("images") or data.get("output_images") or []
        if not img_url and images:
            first = images[0]
            img_url = first.get("url") if isinstance(first, dict) else first
        if not img_url:
            b64 = data.get("b64_json") or data.get("image_base64")
            if b64:
                import base64

                return base64.b64decode(b64)
            raise RuntimeError(f"fluxai: no image in response: {str(data)[:300]}")
        img = client.get(str(img_url))
        img.raise_for_status()
        return img.content


def gen_vendor_openai(prompt: str) -> bytes:
    """Vendor slot as a second OpenAI-compatible images endpoint."""
    key = _vendor_key() or _llm_key()
    if not key:
        raise RuntimeError("IMAGE_VENDOR_API_KEY missing")
    base = _env(
        "IMAGE_VENDOR_URL",
        "IMAGE_PAID2_URL",
        "IMAGE_VENDOR_BASE_URL",
        "IMAGE_PAID2_BASE_URL",
        default="https://api.openai.com/v1",
    ).rstrip("/")
    endpoint = base if base.endswith("/images/generations") else f"{base}/images/generations"
    model = _env("IMAGE_VENDOR_MODEL", "IMAGE_PAID2_MODEL", default="dall-e-3")
    headers = {"content-type": "application/json", "authorization": f"Bearer {key}"}
    with httpx.Client(timeout=180.0) as client:
        r = client.post(
            endpoint,
            headers=headers,
            json={"model": model, "prompt": prompt, "n": 1, "size": "1024x1024"},
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("data") or []
        if not items:
            raise RuntimeError(f"vendor-openai: no data: {data}")
        item = items[0]
        if item.get("b64_json"):
            import base64

            return base64.b64decode(item["b64_json"])
        url = item.get("url")
        if not url:
            raise RuntimeError("vendor-openai: no url")
        img = client.get(url)
        img.raise_for_status()
        return img.content


def gen_vendor_http(prompt: str) -> bytes:
    """Generic POST IMAGE_VENDOR_URL with JSON {prompt}."""
    return gen_fluxai(prompt)


def gen_vendor(prompt: str) -> bytes:
    """Specialty image vendor — IMAGE_VENDOR_PROVIDER."""
    prov = _vendor_provider()
    if prov == "fal":
        return gen_fal(prompt)
    if prov == "pollinations":
        return gen_pollinations(prompt)
    if prov in {"fluxai", "flux"}:
        return gen_fluxai(prompt)
    if prov == "openai":
        return gen_vendor_openai(prompt)
    if prov == "http":
        return gen_vendor_http(prompt)
    raise RuntimeError(
        f"Unknown IMAGE_VENDOR_PROVIDER={prov!r} "
        "(use: fal|pollinations|fluxai|openai|http)"
    )


gen_paid2 = gen_vendor


def _load_workflow(kind: str) -> dict[str, Any]:
    if kind == "gpu":
        name = os.environ.get("COMFYUI_GPU_WORKFLOW") or "flux2_klein_4b.json"
    else:
        pref = (os.environ.get("COMFYUI_CPU_WORKFLOW") or "sdxl").strip().lower()
        if pref in {"sd15", "sd1.5", "sd-1.5"}:
            name = "sd15.json"
        else:
            name = "sdxl.json"
    path = WORKFLOW_DIR / name
    if not path.is_file():
        raise RuntimeError(f"ComfyUI workflow missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _inject_prompt(workflow: dict[str, Any], prompt: str) -> dict[str, Any]:
    replaced = False
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") != "CLIPTextEncode":
            continue
        inputs = node.setdefault("inputs", {})
        text = str(inputs.get("text") or "")
        if "{{PROMPT}}" in text:
            inputs["text"] = prompt
            replaced = True
            break
    if replaced:
        return workflow
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") != "CLIPTextEncode":
            continue
        inputs = node.setdefault("inputs", {})
        text = str(inputs.get("text") or "")
        if "negative" in text.lower() or text.strip().lower() in {
            "",
            "bad quality",
            "bad quality, blurry, lowres",
        }:
            continue
        inputs["text"] = prompt
        return workflow
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "CLIPTextEncode":
            node.setdefault("inputs", {})["text"] = prompt
            break
    return workflow


def _comfy_base(kind: str) -> str:
    if kind == "gpu":
        return (
            os.environ.get("COMFYUI_GPU_URL")
            or os.environ.get("COMFYUI_URL")
            or "http://comfyui-gpu:8188"
        ).rstrip("/")
    return (
        os.environ.get("COMFYUI_CPU_URL")
        or os.environ.get("COMFYUI_URL")
        or "http://comfyui-cpu:8188"
    ).rstrip("/")


def gen_comfy(prompt: str, *, kind: str = "cpu") -> bytes:
    if kind == "gpu" and not _has_gpu():
        raise RuntimeError("COMFYUI_HAS_GPU=0 — skip GPU FLUX path")
    base = _comfy_base(kind)
    workflow = _inject_prompt(_load_workflow(kind), prompt)
    client_id = uuid.uuid4().hex
    timeout = float(os.environ.get("COMFYUI_TIMEOUT") or "300")
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
        try:
            client.get(f"{base}/system_stats").raise_for_status()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"ComfyUI {kind} unreachable at {base}: {e}") from e

        r = client.post(f"{base}/prompt", json={"prompt": workflow, "client_id": client_id})
        r.raise_for_status()
        prompt_id = (r.json() or {}).get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI no prompt_id: {r.text[:300]}")

        deadline = time.time() + timeout
        outputs: dict[str, Any] = {}
        while time.time() < deadline:
            h = client.get(f"{base}/history/{prompt_id}")
            h.raise_for_status()
            hist = h.json() or {}
            entry = hist.get(prompt_id) or {}
            if entry.get("status", {}).get("completed") or entry.get("outputs"):
                outputs = entry.get("outputs") or {}
                if outputs:
                    break
            status = entry.get("status") or {}
            if status.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI error: {status}")
            time.sleep(1.5)
        else:
            raise RuntimeError(f"ComfyUI {kind} timeout after {timeout}s")

        for node_out in outputs.values():
            images = (node_out or {}).get("images") or []
            if not images:
                continue
            meta = images[0]
            params = {
                "filename": meta.get("filename"),
                "subfolder": meta.get("subfolder") or "",
                "type": meta.get("type") or "output",
            }
            img = client.get(f"{base}/view", params=params)
            img.raise_for_status()
            if len(img.content) < 100:
                raise RuntimeError("ComfyUI empty image")
            return img.content
        raise RuntimeError(f"ComfyUI {kind}: no image outputs: {list(outputs.keys())}")


def generate_image_bytes(prompt: str, provider: Optional[str] = None) -> tuple[bytes, str, list[str]]:
    """Try backends in order. Returns (bytes, used_backend, errors)."""
    errors: list[str] = []
    order: list[str] = []
    if provider:
        order.append(_norm_backend(provider))
    for b in image_backends():
        if b not in order:
            order.append(b)
    if "pillow" not in order and (os.environ.get("IMAGE_ALLOW_PILLOW") or "0") == "1":
        order.append("pillow")

    if not order:
        raise RuntimeError("IMAGE_BACKENDS empty — image gen disabled (Low)")

    for b in order:
        if not backend_available(b) and b not in {"pillow", "pollinations"}:
            errors.append(f"{b}: skipped (unavailable)")
            continue
        try:
            if b == "llm":
                return gen_llm(prompt), "llm", errors
            if b in {"vendor", "fal", "fluxai", "flux", "http"}:
                if b != "vendor":
                    prev = os.environ.get("IMAGE_VENDOR_PROVIDER") or os.environ.get(
                        "IMAGE_PAID2_PROVIDER"
                    )
                    try:
                        os.environ["IMAGE_VENDOR_PROVIDER"] = (
                            "fal" if b == "fal" else ("http" if b == "http" else "fluxai")
                        )
                        return gen_vendor(prompt), b, errors
                    finally:
                        if prev is None:
                            os.environ.pop("IMAGE_VENDOR_PROVIDER", None)
                        else:
                            os.environ["IMAGE_VENDOR_PROVIDER"] = prev
                return gen_vendor(prompt), "vendor", errors
            if b in {"comfy-cpu", "comfy_cpu", "cpu"}:
                return gen_comfy(prompt, kind="cpu"), "comfy-cpu", errors
            if b in {"comfy-gpu", "comfy_gpu", "gpu"}:
                return gen_comfy(prompt, kind="gpu"), "comfy-gpu", errors
            if b == "pollinations":
                return gen_pollinations(prompt), "pollinations", errors
            if b == "pillow":
                raise RuntimeError("pillow handled by caller")
            errors.append(f"{b}: unknown backend")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{b}: {e}")
            continue
    raise RuntimeError("all image backends failed: " + "; ".join(errors))
