"""Vision combo infra failures (HTTP/API) — no phrase scan."""
from __future__ import annotations

import json
import re

RETRY_STATUS = {400, 404, 410, 413, 415, 422, 429, 500, 502, 503}


def _api_error(body: str) -> bool:
    raw = (body or "").strip()
    if not raw:
        return False
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    err = payload.get("error")
    if isinstance(err, dict) and str(err.get("message") or "").strip():
        return True
    return isinstance(err, str) and bool(err.strip())


def _content_tokens(text: str) -> set[str]:
    return {w.casefold() for w in re.findall(r"\w+", text or "") if len(w) >= 3}


def vision_text_echoes_prompt(
    text: str,
    prompt: str,
    *,
    min_overlap: float = 0.17,
    min_shared: int = 4,
) -> bool:
    """True when reply mostly restates the describe instruction, not the scene."""
    rt = _content_tokens(text)
    pt = _content_tokens(prompt)
    if not rt or not pt:
        return False
    shared = rt & pt
    if len(shared) < min_shared:
        return False
    return (len(shared) / len(rt)) >= min_overlap


def vision_chunk_usable(text: str, *, min_chars: int = 8) -> bool:
    """Structural describe quality — OCR token dumps only, no phrase scan."""
    t = (text or "").strip()
    if len(t) < min_chars:
        return False
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    words = [w for w in t.replace("\n", " ").split() if w]
    if len(lines) >= 2:
        short_lines = sum(
            1 for ln in lines if len(ln) <= 10 and " " not in ln and len(ln.split()) <= 1
        )
        if short_lines >= 2 and short_lines / len(lines) >= 0.4:
            long_words = [w for w in words if len(w) >= 6]
            if len(long_words) <= 1:
                return False
    return len(words) >= 3


def llm_refused(status: int, body: str, text: str) -> bool:
    """True on transport/API failure — never on chat wording."""
    _ = text
    if status in RETRY_STATUS or status >= 400 or status == 0:
        return True
    return _api_error(body)
