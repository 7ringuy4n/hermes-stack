# -*- coding: utf-8 -*-
"""Optional Dispatcher fast-path for unambiguous office create + text posters.

Compound / ambiguous asks must skip these matchers and go through classify LLM
(see config/classify.json INTENT FAMILIES). Regex here is a gate, not NLU.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

log = logging.getLogger("hermes_plugins.zalo_platform.media_shortcuts")

_OFFICE = re.compile(
    r"(?:tạo|tao|create|make|gen(?:erate)?)\s+.+\b(?:pdf|docx|xlsx|csv|txt|text|markdown|\.md)\b"
    r"|(?:pdf|docx|xlsx|csv|\.txt)\b.+(?:đi[eề]n|dien|ch[uứ]a|chua|ghi|vi[eế]t)",
    re.I | re.S,
)
_POSTER = re.compile(
    r"(?:đi[eề]n|dien|fill|dòng|dong|lines?|poster|chữ|chu ).{0,40}\b(?:dòng|dong|lines?)\b"
    r"|\b\d+\s*(?:dòng|dong|lines?)\b",
    re.I | re.S,
)
_DRAW = re.compile(r"(?:vẽ|ve|draw|image|hình|hinh|ảnh|anh|poster)", re.I)


_OFFICE_KIND = re.compile(
    r"\b(pdf|docx|xlsx|csv|txt|text|markdown|\.md)\b",
    re.I,
)


def _norm_office_kind(token: str) -> str:
    t = (token or "").lower().lstrip(".")
    if t in {"text", "txt"}:
        return "txt"
    if t in {"md", "markdown"}:
        return "md"
    return t


def is_compound_office_request(text: str) -> bool:
    """True when 2+ office kinds appear — leave compound to classify (LLM).

    Do not regex-parse 'sau đó tạo'; only multi-kind detection gates the shortcut.
    """
    raw = (text or "").strip()
    if not raw:
        return False
    kinds = {_norm_office_kind(k) for k in _OFFICE_KIND.findall(raw)}
    return len(kinds) >= 2



def dispatcher_url() -> str:
    return (os.getenv("DISPATCHER_URL") or "http://dispatcher:8090").rstrip("/")


def looks_office_create(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 500:
        return False
    # Compound multi-file asks must not take the single-file Dispatcher shortcut.
    if is_compound_office_request(t):
        return False
    return bool(_OFFICE.search(t))


def looks_text_poster(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 500:
        return False
    if not _DRAW.search(t) and "điền" not in t.lower() and "dien" not in t.lower():
        # Allow "5 dòng hello" without vẽ
        if not re.search(r"\d+\s*(?:dòng|dong|lines?)", t, re.I):
            return False
    try:
        from text_poster import parse_text_poster  # type: ignore
    except ImportError:
        parse_text_poster = None
    if parse_text_poster is not None:
        if parse_text_poster(t):
            return True
    return bool(_POSTER.search(t) and (_DRAW.search(t) or "điền" in t.lower() or "dien" in t.lower()))


def _post(path: str, body: dict, timeout: float = 60.0) -> Dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        dispatcher_url() + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def run_office_create(text: str, thread_id: str, thread_type: str = "user") -> Optional[dict]:
    if not looks_office_create(text):
        return None
    try:
        out = _post(
            "/v1/office-file",
            {
                "prompt": text,
                "thread_id": str(thread_id),
                "thread_type": "group" if str(thread_type).lower() in {"group", "g"} else "user",
                "caption": "",
            },
            timeout=45.0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("office shortcut failed: %s", type(e).__name__)
        return None
    if isinstance(out, dict) and out.get("ok"):
        return out
    return None


def run_text_poster(text: str, thread_id: str = "", thread_type: str = "user") -> Optional[dict]:
    if not looks_text_poster(text):
        return None
    # Prefer importing dispatcher parser when available (same container network only).
    # Hermes calls HTTP; phrase validation stays on Dispatcher.
    name = "poster.png"
    try:
        out = _post(
            "/v1/image",
            {
                "prompt": text,
                "filename": name,
                "refine": False,
                "mode": "text-poster",
            },
            timeout=60.0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("text-poster shortcut failed: %s", type(e).__name__)
        return None
    if isinstance(out, dict) and out.get("ok") and out.get("backend") == "text-poster":
        return out
    # If mode forced but backend wrong, still accept ok file
    if isinstance(out, dict) and out.get("ok"):
        return out
    return None
