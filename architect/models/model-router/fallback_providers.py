"""Capability-aware OpenAI-compatible provider fallbacks.

Provider credentials stay in OpenBao and arrive as process environment values.
Only providers explicitly listed by the operator are used; an absent model means
that provider does not claim the capability.
"""
from __future__ import annotations

import json
import os


CAPABILITY_MODEL_SUFFIX = {
    "chat": "CHAT_MODEL",
    "vision": "VISION_MODEL",
    "embedding": "EMBEDDING_MODEL",
    "image-gen": "IMAGE_MODEL",
    "image-edit": "IMAGE_EDIT_MODEL",
}


def encode_proxy_body(raw: bytes, payload: dict, *, is_json_request: bool) -> bytes:
    """Serialize JSON requests while preserving opaque media bodies exactly."""
    if is_json_request:
        return json.dumps(payload).encode("utf-8")
    return raw


def capability_for_path(path: str, *, has_vision: bool = False) -> str:
    clean = "/" + str(path or "").strip("/").lower()
    if clean.endswith("/chat/completions"):
        return "vision" if has_vision else "chat"
    if clean.endswith("/embeddings"):
        return "embedding"
    if clean.endswith("/images/generations"):
        return "image-gen"
    if clean.endswith("/images/edits"):
        return "image-edit"
    return ""


def configured_fallbacks(capability: str) -> list[tuple[str, str, str, str]]:
    """Return ``(name, base, key, model)`` in operator priority order."""
    suffix = CAPABILITY_MODEL_SUFFIX.get(capability)
    if not suffix:
        return []
    order = (os.environ.get("MODEL_ROUTER_FALLBACK_PROVIDER_ORDER") or "").split(",")
    out: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for raw in order:
        name = raw.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        prefix = name.upper().replace("-", "_")
        base = (os.environ.get(f"{prefix}_API_BASE") or "").strip().rstrip("/")
        key = (os.environ.get(f"{prefix}_API_KEY") or "").strip()
        model = (os.environ.get(f"{prefix}_{suffix}") or "").strip()
        if base and key and model:
            out.append((name, base, key, model))
    return out


def replace_multipart_model(raw: bytes, content_type: str, model: str) -> bytes:
    """Replace only the form field named ``model`` without parsing file data."""
    marker = "boundary="
    if marker not in content_type or not raw or not model:
        return raw
    boundary = content_type.split(marker, 1)[1].split(";", 1)[0].strip().strip('"')
    if not boundary:
        return raw
    delimiter = ("--" + boundary).encode("utf-8")
    parts = raw.split(delimiter)
    for index, part in enumerate(parts):
        head, sep, tail = part.partition(b"\r\n\r\n")
        if not sep or b'name="model"' not in head:
            continue
        ending = b"\r\n" if tail.endswith(b"\r\n") else b""
        parts[index] = head + sep + model.encode("utf-8") + ending
        return delimiter.join(parts)
    return raw


def endpoint_failure_allows_fallback(status: int, body: bytes, capability: str) -> bool:
    if status >= 500 or status in {401, 403, 413, 429}:
        return True
    if status != 400 or capability not in {"embedding", "image-gen", "image-edit"}:
        return False
    detail = body.decode("utf-8", "replace").lower()
    return "target" in detail and ("no " in detail or "unavailable" in detail)
