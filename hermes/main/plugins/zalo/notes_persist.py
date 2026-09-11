# -*- coding: utf-8 -*-
"""Host-owned deferred note persistence after live gather.

When classify sets persist_gathered_notes (or empty note create), Hermes gathers
first. The host POSTs structural note rows from the assistant body into Memory
Manager — listing quality and “new vs prior” semantics belong in skills, not
host NLU.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

# Structural numbered-list protocol only (not user-intent NLU).
_NUMBERED_ITEM_RE = re.compile(r"(?m)^\s*(\d+)[\.\)\-]\s+(.+?)(?=^\s*\d+[\.\)\-]\s+|\Z)", re.S)
# Protocol URL tokens only.
_URL_RE = re.compile(r"https?://[^\s\]\)>\"]+", re.I)


def plan_is_empty_note_create(plan: dict[str, Any] | None) -> bool:
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    if str(src.get("task_hint") or "").strip().lower() != "note":
        return False
    if str(src.get("skill") or "").strip().lower() != "notes":
        return False
    if str(src.get("skill_action") or "").strip().lower() != "create":
        return False
    notes = [n for n in (src.get("notes") or []) if isinstance(n, dict)]
    return not notes


def plan_wants_persist_gathered_notes(plan: dict[str, Any] | None) -> bool:
    """True when classify/skill contract asks the host to persist after gather."""
    if plan_is_empty_note_create(plan):
        return True
    src = plan if isinstance(plan, dict) else {}
    return src.get("persist_gathered_notes") is True


def should_defer_note_persist(plan: dict[str, Any] | None, user_text: str = "") -> bool:
    """True when host must gather first, then persist from the assistant body."""
    _ = user_text  # Intent comes from classify plan fields, not user-text NLU.
    return plan_wants_persist_gathered_notes(plan)


def keep_search_then_note_atomic(plan: dict[str, Any] | None, user_text: str = "") -> bool:
    """Search-then-note must stay one gather+persist turn (no FIFO/workflow split)."""
    return plan_wants_persist_gathered_notes(plan)


def coerce_schedule_fire_plan_for_search_note(
    plan: dict[str, Any] | None, user_text: str = ""
) -> dict[str, Any]:
    """On schedule fire, turn a stored schedule wrapper into executable search work."""
    _ = user_text
    src = dict(plan) if isinstance(plan, dict) else {}
    if not plan_wants_persist_gathered_notes(src):
        return src
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint not in {"schedule", "tool", ""}:
        if hint in {"search", "web_search"} or keep_search_then_note_atomic(src):
            src["process_original_message"] = True
            src["persist_gathered_notes"] = True
        return src
    src["task_hint"] = "search"
    src["task_type"] = "search"
    src["skill"] = "web_search"
    src["execution_class"] = "interactive"
    src["response_mode"] = "final_only"
    src["process_original_message"] = True
    src["persist_gathered_notes"] = True
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    if not parts:
        inner = str(src.get("message") or "").strip()
        if inner:
            src["instructions"] = [inner]
    return src


def strip_false_note_claims(text: str) -> str:
    """Pass-through: skills forbid invented save claims; host does not NLU-filter prose."""
    return str(text or "").strip()


def _today_iso(timezone: str = "Asia/Ho_Chi_Minh") -> str:
    try:
        return date.today().isoformat() if not timezone else __import__(
            "datetime"
        ).datetime.now(ZoneInfo(timezone)).date().isoformat()
    except Exception:
        return date.today().isoformat()


def _normalize_url(url: str) -> str:
    return str(url or "").strip().rstrip(".,;)]}>\"'")


def _urls_in(text: str) -> list[str]:
    seen: list[str] = []
    for match in _URL_RE.finditer(str(text or "")):
        url = _normalize_url(match.group(0))
        if url and url not in seen:
            seen.append(url)
    return seen[:12]


def _host_key(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _urls_for_chunk(chunk: str, global_urls: list[str]) -> list[str]:
    """Prefer URLs inside the item; else match global URLs by hostname token."""
    local = _urls_in(chunk)
    if local:
        return local
    low = chunk.lower()
    matched: list[str] = []
    for url in global_urls:
        host = _host_key(url)
        token = host.split(".")[0] if host else ""
        if token and len(token) >= 3 and token in low and url not in matched:
            matched.append(url)
    return matched[:3]


def _with_citations(content: str, urls: list[str]) -> str:
    body = " ".join(str(content or "").split()).strip()
    if not body:
        return ""
    clean_urls = [u for u in urls if u and u not in body]
    if not clean_urls:
        return body[:4000]
    cite = " | ".join(clean_urls[:3])
    merged = f"{body} Source: {cite}"
    return merged[:4000]


def _notes_skill_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "notes"


def load_search_then_note_contract(*, prior_notes: list[str] | None = None) -> str:
    """Load English skill prompt asset; fill prior note lines when available."""
    path = _notes_skill_dir() / "prompts" / "search_then_note_listing.txt"
    try:
        template = path.read_text(encoding="utf-8")
    except OSError:
        template = (
            "[Search-then-note listing contract]\n"
            "List only concrete openings as Title (stack) — Employer with https URLs.\n"
            "Never list aggregate count buckets. Omit openings already in Prior notes.\n"
            "Do not claim notes were saved; the host persists after this turn.\n"
        )
    prior = [str(x).strip() for x in (prior_notes or []) if str(x).strip()]
    if prior:
        prior_block = "\n".join(f"- {line[:400]}" for line in prior[:40])
    else:
        prior_block = "(none)"
    return template.replace("{{PRIOR_NOTES}}", prior_block).strip()


def notes_from_assistant_body(
    body: str,
    *,
    user_ask: str = "",
    timezone: str = "Asia/Ho_Chi_Minh",
    existing_contents: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Split a gathered assistant answer into durable note payloads with citations.

    Structural only: numbered items + URL attachment. Content policy is skill-owned.
    """
    _ = existing_contents  # Dedup of “already noted” is skill-owned at list time.
    _ = user_ask
    cleaned = strip_false_note_claims(body)
    if not cleaned or len(cleaned) < 3:
        return []
    global_urls = _urls_in(cleaned)
    note_date = _today_iso(timezone)
    items: list[dict[str, Any]] = []
    matches = list(_NUMBERED_ITEM_RE.finditer(cleaned))
    for idx, match in enumerate(matches):
        raw_chunk = str(match.group(2) or "")
        chunk_urls = _urls_for_chunk(raw_chunk, global_urls)
        # Structural pairing: numbered row i ← global URL i when the row has none.
        if not chunk_urls and idx < len(global_urls):
            chunk_urls = [global_urls[idx]]
        chunk = " ".join(raw_chunk.split()).strip()
        if len(chunk) < 3:
            continue
        content = _with_citations(chunk, chunk_urls)
        meta: dict[str, Any] = {"source": "zalo"}
        if chunk_urls:
            meta["citations"] = chunk_urls
        items.append(
            {
                "content": content,
                "note_date": note_date,
                "tags": [],
                "metadata": meta,
            }
        )
    if items:
        return items[:20]
    blob = " ".join(cleaned.split()).strip()
    if len(blob) < 3:
        return []
    content = _with_citations(blob, global_urls)
    meta = {"source": "zalo"}
    if global_urls:
        meta["citations"] = global_urls[:5]
    return [{"content": content, "note_date": note_date, "tags": [], "metadata": meta}]


def simplify_note_query(query: str) -> str:
    """Pass classify selector query through; do not strip language-specific fillers."""
    return " ".join(str(query or "").split()).strip()
