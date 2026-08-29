"""Image generation backends for POST /v1/image.

Fallback order (Media worker default):
  1) comfy-cpu — self-hosted ComfyUI, no VGA (SDXL or SD 1.5)
  2) comfy-gpu — self-hosted ComfyUI + VGA (FLUX.2 [klein] 4B)
  3) omni       — OmniRouter OpenAI-compatible /images/generations

Low: IMAGE_BACKENDS empty → callers get 503.
Comfy skipped when unreachable or no checkpoints installed.
Omni skipped when OMNIROUTER_BASE_URL / OMNIROUTER_API_KEY missing.
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

# Legacy aliases still accepted in IMAGE_BACKENDS for old .env (mapped at runtime).
_BACKEND_ALIASES = {
    "paid1": "omni",
    "paid2": "omni",
    "llm": "omni",
    "vendor": "omni",
    "comfy_cpu": "comfy-cpu",
    "cpu": "comfy-cpu",
    "comfy_gpu": "comfy-gpu",
    "gpu": "comfy-gpu",
}


def _norm_backend(name: str) -> str:
    n = name.strip().lower()
    return _BACKEND_ALIASES.get(n, n)


def _split_backends() -> list[str]:
    raw = os.environ.get("IMAGE_BACKENDS")
    if raw is None:
        return ["comfy-cpu", "comfy-gpu", "omni"]
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


def _has_gpu() -> bool:
    v = (os.environ.get("COMFYUI_HAS_GPU") or "0").strip().lower()
    return v in {"1", "true", "yes", "on"}


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


def _comfy_has_checkpoints(kind: str) -> bool:
    """True when ComfyUI lists at least one real checkpoint (not placeholder dir)."""
    base = _comfy_base(kind)
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
            r = client.get(f"{base}/models/checkpoints")
            r.raise_for_status()
            data = r.json()
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(data, list):
        return False
    for name in data:
        s = str(name or "").strip()
        if not s or "put_checkpoints" in s.lower():
            continue
        return True
    return False


def backend_available(name: str) -> bool:
    n = _norm_backend(name)
    if n in {"comfy-cpu", "comfy_cpu", "cpu"}:
        if not _env("COMFYUI_CPU_URL", "COMFYUI_URL"):
            return False
        return _comfy_has_checkpoints("cpu")
    if n in {"comfy-gpu", "comfy_gpu", "gpu"}:
        if not _has_gpu():
            return False
        if not _env("COMFYUI_GPU_URL", "COMFYUI_URL"):
            return False
        return _comfy_has_checkpoints("gpu")
    if n == "omni":
        base = _env("OMNIROUTER_BASE_URL", default="http://omni-router:20129/v1")
        key = _env("OMNIROUTER_API_KEY")
        enabled = (os.environ.get("ENABLE_OMNIROUTER") or "1").strip().lower()
        if enabled in {"0", "false", "no", "off"}:
            return False
        return bool(base and key)
    if n == "pillow":
        return True
    return False


def gen_omni(prompt: str) -> bytes:
    """Image gen via OmniRouter OpenAI-compatible /images/generations."""
    base = _env("OMNIROUTER_BASE_URL", default="http://omni-router:20129/v1").rstrip("/")
    key = _env("OMNIROUTER_API_KEY")
    if not key:
        raise RuntimeError("OMNIROUTER_API_KEY missing")
    model = _env("IMAGE_OMNI_MODEL", default="dall-e-3")
    size = _env("IMAGE_OMNI_SIZE", default="1024x1024")
    endpoint = base if base.endswith("/images/generations") else f"{base}/images/generations"
    headers = {"content-type": "application/json", "authorization": f"Bearer {key}"}
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "n": 1, "size": size}
    with httpx.Client(timeout=180.0) as client:
        r = client.post(endpoint, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        items = data.get("data") or []
        if not items:
            raise RuntimeError(f"omni: no image data: {str(data)[:300]}")
        item = items[0]
        if item.get("b64_json"):
            import base64

            return base64.b64decode(item["b64_json"])
        url = item.get("url")
        if not url:
            raise RuntimeError(f"omni: no url/b64: {item}")
        img = client.get(url)
        img.raise_for_status()
        return img.content


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


def gen_comfy(prompt: str, *, kind: str = "cpu") -> bytes:
    if kind == "gpu" and not _has_gpu():
        raise RuntimeError("COMFYUI_HAS_GPU=0 — skip GPU FLUX path")
    if not _comfy_has_checkpoints(kind):
        raise RuntimeError(f"ComfyUI {kind}: no checkpoints installed")
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
        if not backend_available(b) and b != "pillow":
            errors.append(f"{b}: skipped (unavailable)")
            continue
        try:
            if b in {"comfy-cpu", "comfy_cpu", "cpu"}:
                return gen_comfy(prompt, kind="cpu"), "comfy-cpu", errors
            if b in {"comfy-gpu", "comfy_gpu", "gpu"}:
                return gen_comfy(prompt, kind="gpu"), "comfy-gpu", errors
            if b == "omni":
                return gen_omni(prompt), "omni", errors
            if b == "pillow":
                raise RuntimeError("pillow handled by caller")
            errors.append(f"{b}: unknown backend")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{b}: {e}")
            continue
    raise RuntimeError("all image backends failed: " + "; ".join(errors))
