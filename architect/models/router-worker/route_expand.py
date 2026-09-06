"""Expand Omni chat candidates: rotate default combo, then free failover models."""
from __future__ import annotations

from typing import Optional


def upstream_url(base: str, path: str) -> str:
    """Join provider base + relative path for the OpenAI proxy.

    When the catch-all route matches ``/v1/chat/completions``, ``path`` is
    ``v1/chat/completions`` even though ``base`` already ends with ``/v1``.
    """
    rel = (path or "").lstrip("/")
    base = (base or "").rstrip("/")
    if base.endswith("/v1") and rel.startswith("v1/"):
        rel = rel[3:].lstrip("/")
    return f"{base}/{rel}"


def direct_ollama_allowed(*, task: str, enable_omni: bool, omni_ok: bool) -> bool:
    """Whether Ollama may appear in the candidate list (always as a *last* hop).

    Normal chat still goes to Omni ``hermes`` first (candidate order + forced
    ``model=hermes``). Omni's combo owns member RR. Ollama must remain available
    after Omni returns 503 inactive/empty — excluding it when Omni was merely
    healthy caused ack-then-silence (no final Zalo reply).
    """
    _ = (task, enable_omni, omni_ok)
    return True


def expand_chat_candidates(
    candidates: list[tuple[str, str, dict[str, str], Optional[str]]],
    *,
    requested_model: str,
    default_model: str = "hermes",
    failover_models: list[str] | None = None,
    rotate_attempts: int = 3,
    has_tools: bool = False,
) -> list[tuple[str, str, dict[str, str], Optional[str]]]:
    """Build ordered upstream hops for chat/completions.

    OmniRoute combos (e.g. ``hermes``) may fall back across members. Retrying the
    same combo id several times lets alive free models answer before we switch
    to explicit failover ids such as ``auto/best-free``.

    When the client sends ``tools``, skip ``auto/*`` failovers — those combos
    do not support tool calling and only add noisy 400 hops.
    """
    failover = [m.strip() for m in (failover_models or []) if (m or "").strip()]
    if has_tools:
        failover = [m for m in failover if not m.lower().startswith("auto/")]
    rotate = max(1, min(int(rotate_attempts or 1), 8))
    out: list[tuple[str, str, dict[str, str], Optional[str]]] = []
    req = (requested_model or "").strip() or (default_model or "hermes")
    failover_seen: set[str] = set()

    for name, base, headers, model_override in candidates:
        if name != "omni-router":
            out.append((name, base, headers, model_override))
            continue
        primary = (model_override or req or default_model or "hermes").strip()
        for _ in range(rotate):
            out.append((name, base, headers, primary))
        for mid in failover:
            if mid == primary or mid in failover_seen:
                continue
            failover_seen.add(mid)
            out.append((name, base, headers, mid))
    return out
