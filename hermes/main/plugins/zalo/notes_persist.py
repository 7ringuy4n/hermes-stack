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
from urllib.parse import urlparse

_FALSE_SAVE_RE = re.compile(
    r"(?im)^.*(?:(?:đã|da)\s+lưu(?:\s+thành)?\s+ghi\s+chú|(?:đã|da)\s+luu(?:\s+thanh)?\s+ghi\s+chu|"
    r"(?:đã|da)\s+lưu\s+ghi\s+chú|note\s+saved|"
    r"(?:đã|da)\s+kiểm\s+tra\s+trước|(?:đã|da)\s+kiem\s+tra\s+truoc|"
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
_URL_RE = re.compile(r"https?://[^\s\]\)>\"]+", re.I)
_DISCLAIMER_SPLIT_RE = re.compile(
    r"(?i)\s+(?:về việc note lại|ve viec note lai|"
    r"mình không (?:có|thể)|minh khong (?:co|the)|"
    r"i (?:can'?t|cannot)|nếu bạn muốn|neu ban muon|"
    r"tổng hợp chung|tong hop chung|"
    r"nguồn các tin cụ thể|nguon cac tin cu the|"
    r"anh/chị muốn|anh/chi muon|bạn muốn mình rà|ban muon minh ra)\b"
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
    # Compound / scheduled process fires still need host persist after gather.
    if text_wants_search_then_note(user_text) and hint in {
        "compound",
        "process",
        "multi",
        "workflow",
        "schedule",
        "tool",
        "",
    }:
        return True
    return False


def keep_search_then_note_atomic(plan: dict[str, Any] | None, user_text: str) -> bool:
    """Search-then-note must stay one gather+persist turn (no FIFO/workflow split)."""
    return should_defer_note_persist(plan, user_text) or text_wants_search_then_note(user_text)


_TIMING_PREFIX_RE = re.compile(
    r"(?is)^\s*(?:"
    r"(?:\d+)\s*(?:phút|phut|minute|minutes|min|giây|giay|second|seconds|s|"
    r"giờ|gio|hour|hours|h)\s*(?:nữa|nua|sau|later)?|"
    r"(?:sau|in)\s+(?:\d+)\s*(?:phút|phut|minute|minutes|min|giây|giay|second|seconds|"
    r"giờ|gio|hour|hours|h)|"
    r"(?:ngày mai|ngay mai|tomorrow|tonight|tối nay|toi nay)"
    r")\s*[,:]?\s*"
)


def strip_schedule_timing_prefix(text: str) -> str:
    """Drop leading relative timing so schedule fire_text can hold inner work."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    stripped = _TIMING_PREFIX_RE.sub("", raw, count=1).strip()
    return stripped if stripped and stripped != raw else ""


def coerce_schedule_fire_plan_for_search_note(
    plan: dict[str, Any] | None, user_text: str
) -> dict[str, Any]:
    """On schedule fire, turn a stored schedule wrapper into executable search work."""
    src = dict(plan) if isinstance(plan, dict) else {}
    if not text_wants_search_then_note(user_text):
        return src
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint not in {"schedule", "tool", ""}:
        # Already executable, but still ensure search contract fields.
        if hint in {"search", "web_search"} or keep_search_then_note_atomic(src, user_text):
            src["process_original_message"] = True
        return src
    src["task_hint"] = "search"
    src["task_type"] = "search"
    src["skill"] = "web_search"
    src["execution_class"] = "interactive"
    src["response_mode"] = "final_only"
    src["process_original_message"] = True
    # Prefer fire/inner instructions; if empty, use timing-stripped ask.
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    if not parts:
        inner = strip_schedule_timing_prefix(user_text) or str(user_text or "").strip()
        if inner:
            src["instructions"] = [inner]
    return src


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
        ("topdev", "topdev"),
    ):
        if token in low and tag not in tags:
            tags.append(tag)
    return tags[:12]


def _normalize_url(url: str) -> str:
    raw = str(url or "").strip().rstrip(".,;)]}>\"'")
    return raw


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
    """Prefer URLs inside the item; else match global source URLs by host/token."""
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
    # If the item names a known board but no host match, keep board URLs briefly.
    if not matched:
        for url in global_urls:
            host = _host_key(url)
            if any(x in host for x in ("itviec", "topcv", "topdev", "facebook", "linkedin")):
                # Only attach when the chunk mentions that board name.
                board = next(
                    (b for b in ("itviec", "topcv", "topdev", "facebook", "linkedin") if b in host),
                    "",
                )
                if board and board in low and url not in matched:
                    matched.append(url)
    return matched[:3]


def _with_citations(content: str, urls: list[str]) -> str:
    body = " ".join(str(content or "").split()).strip()
    if not body:
        return ""
    clean_urls = [u for u in urls if u and u not in body]
    if not clean_urls:
        # Still keep existing in-body URLs as the citation signal.
        return body[:4000]
    cite = " | ".join(clean_urls[:3])
    merged = f"{body} Nguồn: {cite}"
    return merged[:4000]


def notes_from_assistant_body(
    body: str,
    *,
    user_ask: str = "",
    timezone: str = "Asia/Ho_Chi_Minh",
) -> list[dict[str, Any]]:
    """Split a gathered assistant answer into durable note payloads with citations."""
    cleaned = strip_false_note_claims(body)
    if not cleaned or len(cleaned) < 3:
        return []
    global_urls = _urls_in(cleaned)
    # Drop trailing soft questions / offers / agent storage disclaimers.
    cleaned = re.sub(
        r"(?is)\n+\s*(?:bạn có muốn|you (?:want|can)|muốn mình|về việc note lại|"
        r"mình không (?:có quyền|thể)|i (?:can'?t|cannot) (?:save|store|note)|"
        r"không thể xác nhận đã lưu|chưa xác nhận được việc note|"
        r"nếu bạn muốn mình lưu|anh/chị muốn|bạn muốn mình rà).*$",
        "",
        cleaned,
    ).strip()
    # Drop summary blocks that are not numbered job items.
    cleaned = re.sub(
        r"(?is)\n+\s*(?:tổng hợp chung|nguồn các tin cụ thể).*$",
        "",
        cleaned,
    ).strip()
    note_date = _today_iso(timezone)
    tags = _tags_from_ask(user_ask)
    items: list[dict[str, Any]] = []
    for match in _NUMBERED_ITEM_RE.finditer(cleaned):
        raw_chunk = str(match.group(2) or "")
        chunk_urls = _urls_for_chunk(raw_chunk, global_urls)
        chunk = " ".join(raw_chunk.split())
        chunk = _DISCLAIMER_SPLIT_RE.split(chunk, maxsplit=1)[0].strip()
        if len(chunk) < 3:
            continue
        # Skip pure meta / non-job numbered leftovers.
        low = chunk.lower()
        if low.startswith(("tổng hợp", "nguồn", "lưu ý")):
            continue
        content = _with_citations(chunk, chunk_urls)
        meta: dict[str, Any] = {"source": "zalo"}
        if chunk_urls:
            meta["citations"] = chunk_urls
        items.append(
            {
                "content": content,
                "note_date": note_date,
                "tags": list(tags),
                "metadata": meta,
            }
        )
    if items:
        return items[:20]
    # Single blob when the model did not number results.
    blob = " ".join(cleaned.split())
    blob = _DISCLAIMER_SPLIT_RE.split(blob, maxsplit=1)[0].strip()
    if len(blob) < 3:
        return []
    content = _with_citations(blob, global_urls)
    meta = {"source": "zalo"}
    if global_urls:
        meta["citations"] = global_urls[:5]
    return [{"content": content, "note_date": note_date, "tags": list(tags), "metadata": meta}]


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
        "hôm",
        "hom",
        "nay",
        "bao",
        "nhiều",
        "nhieu",
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
