# -*- coding: utf-8 -*-
"""Host-owned deferred note persistence after live gather.

When classify asks to note content that does not exist yet (empty notes[]
create, or search-then-note), Hermes gathers first. The host must POST the
resulting assistant body into Memory Manager — the agent must never own
storage claims.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

_FALSE_SAVE_RE = re.compile(
    r"(?im)^.*(?:(?:đã|da)\s+lưu(?:\s+thành)?\s+ghi\s+chú|(?:đã|da)\s+luu(?:\s+thanh)?\s+ghi\s+chu|"
    r"note\s+saved|(?:đã|da)\s+kiểm\s+tra\s+trước|(?:đã|da)\s+kiem\s+tra\s+truoc|"
    r"mình không thể tự lưu note|không thể tự lưu note|"
    r"chưa xác nhận được việc note|chưa thể xác nhận đã lưu).*$"
)
_NUMBERED_ITEM_RE = re.compile(r"(?m)^\s*(\d+)[\.\)\-]\s+(.+?)(?=^\s*\d+[\.\)\-]\s+|\Z)", re.S)
_NOTE_AFTER_SEARCH_RE = re.compile(
    r"(?is)(?:tìm|tim|search|find|tra\s*cứu|truy\s*cập).{0,160}"
    r"(?:note|ghi\s*chú|ghi\s*lại|lưu\s*lại|note\s*lại)"
)
_NOTE_VERB_RE = re.compile(
    r"(?is)\b(?:note|ghi\s*chú|ghi\s*lại|lưu\s*lại|note\s*lại)\b"
)


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


def text_wants_search_then_note(text: str) -> bool:
    blob = str(text or "").strip()
    if not blob:
        return False
    if _NOTE_AFTER_SEARCH_RE.search(blob):
        return True
    return bool(_NOTE_VERB_RE.search(blob) and re.search(r"(?is)\b(?:tìm|tim|search|find)\b", blob))


def should_defer_note_persist(plan: dict[str, Any] | None, user_text: str) -> bool:
    """True when host must gather first, then persist from the assistant body."""
    if plan_is_empty_note_create(plan):
        return True
    src = plan if isinstance(plan, dict) else {}
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint in {"search", "web_search", "normal", "unknown", "chat"} and text_wants_search_then_note(
        user_text
    ):
        return True
    if hint == "search" and text_wants_search_then_note(user_text):
        return True
    return False


def strip_false_note_claims(text: str) -> str:
    """Remove invented host confirmations from an agent reply before send/store."""
    lines = []
    for line in str(text or "").splitlines():
        if _FALSE_SAVE_RE.match(line.strip()):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _today_iso(timezone: str = "Asia/Ho_Chi_Minh") -> str:
    try:
        return date.today().isoformat() if not timezone else __import__(
            "datetime"
        ).datetime.now(ZoneInfo(timezone)).date().isoformat()
    except Exception:
        return date.today().isoformat()


def _tags_from_ask(user_ask: str) -> list[str]:
    low = str(user_ask or "").lower()
    tags: list[str] = []
    for token, tag in (
        ("java", "java"),
        ("fullstack", "fullstack"),
        ("full-stack", "fullstack"),
        ("full stack", "fullstack"),
        ("backend", "backend"),
        ("be ", "backend"),
        ("tuyển dụng", "tuyển-dụng"),
        ("tuyen dung", "tuyển-dụng"),
        ("facebook", "facebook"),
        ("itviec", "itviec"),
        ("topcv", "topcv"),
    ):
        if token in low and tag not in tags:
            tags.append(tag)
    return tags[:12]


def notes_from_assistant_body(
    body: str,
    *,
    user_ask: str = "",
    timezone: str = "Asia/Ho_Chi_Minh",
) -> list[dict[str, Any]]:
    """Split a gathered assistant answer into durable note payloads."""
    cleaned = strip_false_note_claims(body)
    if not cleaned or len(cleaned) < 3:
        return []
    # Drop trailing soft questions / offers / agent storage disclaimers.
    cleaned = re.sub(
        r"(?is)\n+\s*(?:bạn có muốn|you (?:want|can)|muốn mình|về việc note lại|"
        r"mình không (?:có quyền|thể)|i (?:can'?t|cannot) (?:save|store|note)|"
        r"không thể xác nhận đã lưu|chưa xác nhận được việc note|"
        r"nếu bạn muốn mình lưu).*$",
        "",
        cleaned,
    ).strip()
    note_date = _today_iso(timezone)
    tags = _tags_from_ask(user_ask)
    items: list[dict[str, Any]] = []
    for match in _NUMBERED_ITEM_RE.finditer(cleaned):
        chunk = " ".join(str(match.group(2) or "").split())
        # Keep only the first sentence/line of a numbered block when the model
        # appends meta commentary after the job title.
        chunk = re.split(
            r"(?i)\s+(?:về việc note lại|mình không (?:có|thể)|i (?:can'?t|cannot)|"
            r"nếu bạn muốn)\b",
            chunk,
            maxsplit=1,
        )[0].strip()
        if len(chunk) < 3:
            continue
        items.append({"content": chunk[:4000], "note_date": note_date, "tags": list(tags)})
    if items:
        return items[:20]
    # Single blob when the model did not number results.
    blob = " ".join(cleaned.split())
    if len(blob) < 3:
        return []
    return [{"content": blob[:4000], "note_date": note_date, "tags": list(tags)}]


def simplify_note_query(query: str) -> str:
    """Drop Vietnamese/English filler so FTS/ILIKE can match stored payloads."""
    raw = " ".join(str(query or "").split())
    if not raw:
        return ""
    stop = {
        "hiển",
        "hien",
        "thị",
        "thi",
        "các",
        "cac",
        "cái",
        "cai",
        "tin",
        "đã",
        "da",
        "lưu",
        "luu",
        "ghi",
        "chú",
        "chu",
        "note",
        "notes",
        "cho",
        "tôi",
        "toi",
        "của",
        "cua",
        "the",
        "a",
        "an",
        "my",
        "saved",
        "show",
        "list",
        "display",
        "xem",
        "những",
        "nhung",
        # Topic fillers that rarely appear verbatim in stored job lines.
        "tuyển",
        "tuyen",
        "dụng",
        "dung",
        "việc",
        "viec",
        "làm",
        "lam",
        "job",
        "jobs",
        "recruitment",
    }
    keep: list[str] = []
    for token in re.split(r"[^\w+#]+", raw, flags=re.UNICODE):
        t = token.strip().lower()
        if len(t) < 2 or t in stop:
            continue
        keep.append(token.strip())
    return " ".join(keep) if keep else raw
