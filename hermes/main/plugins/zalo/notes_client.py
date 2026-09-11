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
    return {
        "scope_id": scope_id,
        "id": str(selector.get("id") or "").strip() or None,
        "query": str(selector.get("query") or "").strip(),
        "date_from": selector.get("date_from"),
        "date_to": selector.get("date_to"),
        "tags": list(selector.get("tags") or []),
        "limit": 20,
    }


def _find_candidates(scope_id: str, selector: dict[str, Any]) -> list[dict[str, Any]]:
    data = _request("POST", "/v1/notes/query", _selector_payload(scope_id, selector))
    items = data.get("items") if isinstance(data.get("items"), list) else []
    return [item for item in items if isinstance(item, dict)]


def _candidate_lines(items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in items[:10]:
        prefix = str(item.get("note_date") or "undated")
        content = str(item.get("content") or "").strip().replace("\n", " ")
        lines.append(f"- [{prefix}] {content[:400]} (id: {item.get('id')})")
    return "\n".join(lines)


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
                    "content": item.get("content"),
                    "note_date": item.get("note_date"),
                    "thread_id": thread_id,
                    "thread_type": thread_type,
                    "owner_id": sender_id,
                    "tags": list(item.get("tags") or []),
                    "metadata": {"source": "zalo"},
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
        return {
            "success": True,
            "action": action,
            "count": len(candidates),
            "items": candidates,
            "text": _candidate_lines(candidates),
        }

    if action not in {"update", "delete"}:
        return {"success": False, "error": "unsupported_action"}
    if not candidates:
        return {"success": False, "error": "not_found"}
    if len(candidates) != 1 or plan.get("uncertain") is True:
        return {
            "success": False,
            "error": "ambiguous",
            "count": len(candidates),
            "text": _candidate_lines(candidates),
        }

    note_id = str(candidates[0].get("id") or "")
    if action == "delete":
        path = "/v1/notes/" + urllib.parse.quote(note_id, safe="")
        path += "?scope_id=" + urllib.parse.quote(scope_id, safe="")
        return _request("DELETE", path)
    if len(notes) != 1:
        return {"success": False, "error": "missing_update"}
    replacement = notes[0]
    return _request(
        "PATCH",
        "/v1/notes/" + urllib.parse.quote(note_id, safe=""),
        {
            "scope_id": scope_id,
            "content": replacement.get("content"),
            "note_date": replacement.get("note_date"),
            "tags": list(replacement.get("tags") or []),
        },
    )


async def execute_note_plan_async(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(execute_note_plan, *args, **kwargs)
