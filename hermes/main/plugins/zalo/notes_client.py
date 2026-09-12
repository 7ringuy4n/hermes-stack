"""Typed client for scoped, durable notes in Memory Manager."""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def memory_url() -> str:
    return (os.environ.get("MEMORY_URL") or "http://memory:8095").rstrip("/")


def note_scope(*, thread_id: str, thread_type: str, sender_id: str) -> str:
    if str(thread_type or "").strip().lower() == "group":
        return f"zalo:group:{str(thread_id).strip()}"
    return f"zalo:user:{str(sender_id).strip()}"


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        memory_url() + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    timeout = max(2.0, min(float(os.environ.get("NOTES_HTTP_TIMEOUT_S") or "8"), 30.0))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        return data if isinstance(data, dict) else {"success": False, "error": "invalid_response"}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return {"success": False, "error": f"http_{exc.code}", "detail": detail}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"success": False, "error": type(exc).__name__}


def _selector_payload(scope_id: str, selector: dict[str, Any]) -> dict[str, Any]:
    try:
        limit = int(selector.get("limit") or 10)
    except (TypeError, ValueError):
        limit = 10
    return {
        "scope_id": scope_id,
        "id": str(selector.get("id") or "").strip() or None,
        "query": str(selector.get("query") or "").strip(),
        "date_from": selector.get("date_from"),
        "date_to": selector.get("date_to"),
        "tags": list(selector.get("tags") or []),
        "limit": max(1, min(limit, 1000)),
    }


def _find_candidates(scope_id: str, selector: dict[str, Any]) -> list[dict[str, Any]]:
    data = _request("POST", "/v1/notes/query", _selector_payload(scope_id, selector))
    items = data.get("items") if isinstance(data.get("items"), list) else []
    return [item for item in items if isinstance(item, dict)]


def list_existing_note_contents(
    *,
    thread_id: str,
    thread_type: str,
    sender_id: str,
    query: str = "",
    tags: list[str] | None = None,
    limit: int = 50,
) -> list[str]:
    """Return prior note bodies for soft dedupe before deferred create."""
    scope_id = note_scope(thread_id=thread_id, thread_type=thread_type, sender_id=sender_id)
    selector = {
        "query": str(query or "").strip(),
        "tags": list(tags or [])[:12],
        "limit": max(1, min(int(limit or 50), 100)),
    }
    items = _find_candidates(scope_id, selector)
    # Broad fallback: scope-wide recent notes when the topic query is empty/misses.
    if not items and (selector["query"] or selector["tags"]):
        items = _find_candidates(scope_id, {"query": "", "tags": [], "limit": selector["limit"]})
    out: list[str] = []
    for item in items:
        content = str(item.get("content") or "").strip()
        if content and content not in out:
            out.append(content)
    return out


def _candidate_lines(items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, item in enumerate(items[:10], start=1):
        prefix = str(item.get("note_date") or "—")
        title = str(item.get("title") or "").strip()
        if not title:
            title = str(item.get("content") or "").strip().splitlines()[0][:120]
        lines.append(f"{index}. [{prefix}] {title[:160]} (id: {item.get('id')})")
    return "\n".join(lines)


def _detail_text(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    content = str(item.get("content") or "").strip()
    if not title:
        title = content.splitlines()[0][:160] if content else "Note"
    date_text = str(item.get("note_date") or "—")
    meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    citations = [str(x).strip() for x in (meta.get("citations") or []) if str(x).strip()]
    cite_line = "\n\nSources: " + " | ".join(citations[:5]) if citations else ""
    return f"{title}\n[{date_text}]\n\n{content}{cite_line}".strip()


def execute_note_plan(
    plan: dict[str, Any],
    *,
    thread_id: str,
    thread_type: str,
    sender_id: str,
) -> dict[str, Any]:
    """Execute a validated note plan; never select an ambiguous mutation target."""
    scope_id = note_scope(thread_id=thread_id, thread_type=thread_type, sender_id=sender_id)
    action = str(plan.get("skill_action") or "").strip().lower()
    notes = [item for item in (plan.get("notes") or []) if isinstance(item, dict)]
    selector = plan.get("note_selector") if isinstance(plan.get("note_selector"), dict) else {}

    if action == "create":
        if not notes:
            return {"success": False, "error": "missing_notes"}
        created: list[dict[str, Any]] = []
        for item in notes:
            result = _request(
                "POST",
                "/v1/notes",
                {
                    "scope_id": scope_id,
                    "title": item.get("title"),
                    "content": item.get("content"),
                    "note_date": item.get("note_date"),
                    "thread_id": thread_id,
                    "thread_type": thread_type,
                    "owner_id": sender_id,
                    "tags": list(item.get("tags") or []),
                    "metadata": (
                        dict(item.get("metadata"))
                        if isinstance(item.get("metadata"), dict)
                        else {"source": "zalo"}
                    ),
                },
            )
            if not result.get("success"):
                return result
            created.append(result.get("note") or {})
        return {"success": True, "action": action, "count": len(created), "items": created}

    try:
        from .notes_persist import simplify_note_query
    except ImportError:
        from notes_persist import simplify_note_query  # type: ignore

    mutation = action in {"update", "delete"}
    if mutation:
        selector = dict(selector)
        selector["limit"] = 1000
    candidates = _find_candidates(scope_id, selector)
    # Topic lookups often include filler ("hiển thị các tin … đã lưu"). Retry
    # with a simplified query, then with individual strong tokens.
    if action == "lookup" and not candidates:
        raw_q = str(selector.get("query") or "").strip()
        simple = simplify_note_query(raw_q)
        tried = {raw_q}
        for attempt in [simple, *sorted((simple or "").split(), key=len, reverse=True)]:
            token = " ".join(str(attempt or "").split())
            if not token or token in tried or len(token) < 2:
                continue
            tried.add(token)
            retry = dict(selector)
            retry["query"] = token
            candidates = _find_candidates(scope_id, retry)
            if candidates:
                break
    if action == "lookup":
        view = str(selector.get("view") or "list").strip().lower()
        if view == "count":
            text = f"{len(candidates)} note(s)."
        elif view == "detail" and len(candidates) == 1:
            text = _detail_text(candidates[0])
        else:
            text = _candidate_lines(candidates)
        return {
            "success": True,
            "action": action,
            "count": len(candidates),
            "items": candidates,
            "text": text,
        }

    if action not in {"update", "delete"}:
        return {"success": False, "error": "unsupported_action"}
    if not candidates:
        return {"success": False, "error": "not_found"}
    bulk_authorized = selector.get("match_all") is True or selector.get("bulk") is True
    if (len(candidates) != 1 and not bulk_authorized) or plan.get("uncertain") is True:
        return {
            "success": False,
            "error": "ambiguous",
            "count": len(candidates),
            "text": _candidate_lines(candidates),
        }

    if action == "delete":
        deleted: list[str] = []
        for candidate in candidates:
            note_id = str(candidate.get("id") or "")
            if not note_id:
                continue
            path = "/v1/notes/" + urllib.parse.quote(note_id, safe="")
            path += "?scope_id=" + urllib.parse.quote(scope_id, safe="")
            result = _request("DELETE", path)
            if not result.get("success"):
                return {**result, "count": len(deleted)}
            deleted.append(note_id)
        return {"success": True, "action": action, "count": len(deleted), "ids": deleted}
    if len(notes) != 1:
        return {"success": False, "error": "missing_update"}
    replacement = notes[0]
    updated: list[dict[str, Any]] = []
    for candidate in candidates:
        note_id = str(candidate.get("id") or "")
        if not note_id:
            continue
        result = _request(
            "PATCH",
            "/v1/notes/" + urllib.parse.quote(note_id, safe=""),
            {
                "scope_id": scope_id,
                "title": replacement.get("title"),
                "content": replacement.get("content"),
                "note_date": replacement.get("note_date"),
                "tags": list(replacement.get("tags") or []),
            },
        )
        if not result.get("success"):
            return {**result, "count": len(updated)}
        updated.append(result.get("note") or {})
    return {"success": True, "action": action, "count": len(updated), "items": updated}


async def execute_note_plan_async(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(execute_note_plan, *args, **kwargs)
