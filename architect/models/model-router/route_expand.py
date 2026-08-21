"""Expand Omni chat candidates: rotate default combo, then free failover models."""
from __future__ import annotations

from typing import Optional


def expand_chat_candidates(
    candidates: list[tuple[str, str, dict[str, str], Optional[str]]],
    *,
    requested_model: str,
    default_model: str = "hermes",
    failover_models: list[str] | None = None,
    rotate_attempts: int = 3,
) -> list[tuple[str, str, dict[str, str], Optional[str]]]:
    """Build ordered upstream hops for chat/completions.

    OmniRouter combos (e.g. ``hermes``) round-robin free members. Retrying the
    same combo id several times lets alive free models answer before we switch
    to explicit failover ids such as ``auto/best-free``.
    """
    failover = [m.strip() for m in (failover_models or []) if (m or "").strip()]
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
