"""HTTP client for zalo-api channel registry (user/group id ↔ name).

Used so schedules can target a Zalo group by display name while keeping
requester user id on the schedule origin for audit.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Optional

# Allow-list / admin status phrases — never treat as a group display name.
_GROUP_REF_NOISE_RE = re.compile(
    r"(?i)^\s*(?:"
    r"đã\s*allow(?:\s*\(\s*\d+\s*\))?|"
    r"da\s*allow(?:\s*\(\s*\d+\s*\))?|"
    r"already\s*allow(?:ed)?(?:\s*\(\s*\d+\s*\))?|"
    r"allow(?:ed)?\s*\(\s*\d+\s*\)|"
    r"nhóm\s+đã\s*allow(?:\s*\(\s*\d+\s*\))?|"
    r"nhom\s+da\s*allow(?:\s*\(\s*\d+\s*\))?|"
    r"groups?\s+already\s*allow(?:ed)?"
    r")\s*$"
)


def _api_base() -> str:
    return (
        os.getenv("ZALO_API_URL")
        or os.getenv("ADMIN_API_URL")
        or "http://zalo-api:8100"
    ).rstrip("/")


def _headers() -> dict[str, str]:
    token = (
        os.getenv("ZALO_API_TOKEN") or os.getenv("ADMIN_API_TOKEN") or ""
    ).strip()
    out = {"Content-Type": "application/json"}
    if token:
        out["Authorization"] = f"Bearer {token}"
    return out


def _req(method: str, path: str, payload: Optional[dict] = None, timeout: float = 8.0) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(
        _api_base() + path,
        data=data,
        method=method,
        headers=_headers() if data or method != "GET" else (
            {k: v for k, v in _headers().items() if k != "Content-Type"}
        ),
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {}


def upsert_channel(
    *,
    external_id: str,
    name: str = "",
    kind: str = "group",
    platform: str = "zalo",
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    eid = (external_id or "").strip()
    if not eid:
        return {}
    body: dict[str, Any] = {
        "platform": platform,
        "external_id": eid,
        "name": (name or "").strip(),
        "kind": kind,
    }
    if meta:
        body["meta"] = meta
    return _req("POST", "/v1/channels/upsert", body)


def resolve_channel(ref: str, *, platform: str = "zalo") -> Optional[dict[str, Any]]:
    needle = (ref or "").strip()
    if not needle:
        return None
    data = _req("POST", "/v1/channels/resolve", {"platform": platform, "ref": needle})
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    ch = data.get("channel")
    return ch if isinstance(ch, dict) else None


def remember_inbound(
    *,
    thread_id: str,
    thread_type: str,
    sender_id: str = "",
    sender_name: str = "",
    thread_name: str = "",
) -> None:
    """Best-effort: store user + thread ids seen on inbound traffic."""
    tid = (thread_id or "").strip()
    sid = (sender_id or "").strip()
    kind = "group" if str(thread_type or "").lower() in {"group", "g"} else "user"
    if tid:
        upsert_channel(
            external_id=tid,
            name=(thread_name or (sender_name if kind == "user" else "")).strip(),
            kind=kind,
            meta={"source": "inbound"},
        )
    if sid and sid != tid:
        upsert_channel(
            external_id=sid,
            name=(sender_name or "").strip(),
            kind="user",
            meta={"source": "inbound"},
        )


def _clean_group_ref(raw: str) -> str:
    ref = (raw or "").strip(" \t\"'“”.:-")
    if not ref or _GROUP_REF_NOISE_RE.match(ref):
        return ""
    # Strip channel platform prefixes so classify "zalo LC group" → "LC group"
    # (same variants as zalo-api channels_registry.resolve).
    low = ref.lower()
    for prefix in (
        "zalo ",
        "telegram ",
        "lark ",
        "discord ",
        "slack ",
        "whatsapp ",
    ):
        if low.startswith(prefix):
            stripped = ref[len(prefix) :].strip(" \t\"'“”.:-")
            if stripped:
                ref = stripped
            break
    if not ref or _GROUP_REF_NOISE_RE.match(ref):
        return ""
    return ref


def extract_target_group_ref(text: str, plan: Optional[dict[str, Any]] = None) -> str:
    """Display name from classify JSON only. Host does not phrase-scan the bubble."""
    del text  # destination is not inferred from user prose
    src = plan if isinstance(plan, dict) else {}
    for key in ("target_channel", "deliver_to", "target_group", "group_name"):
        val = _clean_group_ref(str(src.get(key) or ""))
        if val:
            return val
    return ""


def apply_schedule_delivery_target(
    *,
    text: str,
    plan: dict[str, Any],
    origin: dict[str, Any],
    context: dict[str, Any],
    current_thread_type: str,
) -> tuple[dict[str, Any], dict[str, Any], Optional[str]]:
    """Rewrite origin/context when the user asked to deliver into a named group.

    Returns (origin, context, note). note is set when a named target was resolved
    or when resolution failed (caller may surface it).
    """
    ref = extract_target_group_ref(text, plan)
    if not ref:
        return origin, context, None
    # Already in that group and ref looks like current thread — keep as-is.
    cur_tid = str(origin.get("thread_id") or origin.get("chat_id") or "")
    if str(current_thread_type or "").lower() in {"group", "g"} and (
        ref == cur_tid or ref.lower() == str(origin.get("chat_name") or "").lower()
    ):
        return origin, context, None

    hit = resolve_channel(ref)
    if not hit:
        return origin, context, f"group_not_found:{ref}"
    kind = str(hit.get("kind") or "group").lower()
    if kind not in {"group", "g"}:
        # Scheduling to a user DM by name is allowed but rare.
        pass
    gid = str(hit.get("external_id") or "").strip()
    gname = str(hit.get("name") or ref).strip()
    if not gid:
        return origin, context, f"group_not_found:{ref}"
    requester = str(origin.get("user_id") or context.get("sender_id") or "").strip()
    requester_name = str(origin.get("chat_name") or context.get("sender_name") or "").strip()
    new_origin = dict(origin)
    new_origin.update(
        {
            "chat_id": gid,
            "thread_id": gid,
            "chat_name": gname,
            "user_id": requester or new_origin.get("user_id"),
            "requester_id": requester,
            "requester_name": requester_name,
            "target_name": gname,
        }
    )
    new_context = dict(context)
    new_context.update(
        {
            "thread_id": gid,
            "thread_type": "group" if kind in {"group", "g"} else "user",
            "chat_type": "group" if kind in {"group", "g"} else "dm",
            "sender_id": requester or str(new_context.get("sender_id") or ""),
            "sender_name": requester_name or str(new_context.get("sender_name") or ""),
            "target_channel": gname,
        }
    )
    return new_origin, new_context, f"deliver_to:{gname}"
