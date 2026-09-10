"""Locale-aware UX copy. Operators edit messages/ux.json; no language in code.

Language is inferred from Unicode script in the user text (not keyword lists).
Add more locale keys in ux.json — unknown languages fall back to ``en``.
"""
from __future__ import annotations

import re
from typing import Any

_VI_LATIN = re.compile(
    r"[ăâêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵđ"
    r"ĂÂÊÔƠƯÁÀẢÃẠÉÈẺẼẸÍÌỈĨỊÓÒỎÕỌÚÙỦŨỤÝỲỶỸỴĐ]"
)
_HANGUL = re.compile(r"[\uac00-\ud7af]")
_KANA = re.compile(r"[\u3040-\u30ff]")
_HAN = re.compile(r"[\u3400-\u9fff]")
_ARABIC = re.compile(r"[\u0600-\u06ff]")
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")
_THAI = re.compile(r"[\u0e00-\u0e7f]")


def reply_lang(text: str) -> str:
    raw = text or ""
    if _VI_LATIN.search(raw):
        return "vi"
    if _HANGUL.search(raw):
        return "ko"
    if _KANA.search(raw):
        return "ja"
    if _HAN.search(raw):
        return "zh"
    if _ARABIC.search(raw):
        return "ar"
    if _CYRILLIC.search(raw):
        return "ru"
    if _THAI.search(raw):
        return "th"
    return "en"


def pick_localized(spec: Any, lang: str, fallback: str) -> str:
    """String copy, or ``{locale: copy}`` map. ``default`` may be a locale id or copy."""
    if isinstance(spec, str) and spec.strip():
        return spec.strip()
    if not isinstance(spec, dict):
        return fallback
    keys: list[str] = []
    if lang:
        keys.append(str(lang).strip().lower())
    alias = spec.get("default")
    if isinstance(alias, str) and alias.strip():
        token = alias.strip()
        if len(token) <= 8 and token.replace("-", "").isalpha():
            keys.append(token.lower())
    keys.append("en")
    seen: set[str] = set()
    for key in keys:
        if not key or key in seen:
            continue
        seen.add(key)
        val = spec.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    if isinstance(alias, str) and len(alias.strip()) > 8:
        return alias.strip()
    for val in spec.values():
        if isinstance(val, str) and val.strip() and val.strip().lower() not in seen:
            if len(val.strip()) > 8:
                return val.strip()
    return fallback
