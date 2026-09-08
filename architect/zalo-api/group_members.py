"""Parse complete Zalo group-member snapshots without provider-specific guesses."""
from __future__ import annotations

from typing import Any, Optional


def group_record(info: Any, thread_id: str) -> dict[str, Any]:
    """Return the group record nested in a bridge getGroupInfo response."""
    if not isinstance(info, dict):
        return {}
    tid = str(thread_id or "").strip()
    for key in ("gridInfoMap", "grid_info_map", "groups"):
        nested = info.get(key)
        if not isinstance(nested, dict):
            continue
        record = nested.get(tid)
        if isinstance(record, dict):
            return record
        if len(nested) == 1:
            only = next(iter(nested.values()))
            if isinstance(only, dict):
                return only
    return info


def _member(entry: Any, *, versioned: bool) -> tuple[str, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    value: Any = entry
    if isinstance(entry, dict):
        value = (
            entry.get("zaloUserId")
            or entry.get("userId")
            or entry.get("uid")
            or entry.get("id")
            or ""
        )
        metadata = {
            str(key): item
            for key, item in entry.items()
            if key not in {"zaloUserId", "userId", "uid", "id"}
        }
    text = str(value or "").strip()
    if versioned:
        uid, separator, version = text.partition("_")
        text = uid.strip()
        if separator and version:
            metadata["version"] = version
    if not text.isdigit():
        return "", {}
    return text, metadata


def _identity_set(record: dict[str, Any], keys: tuple[str, ...]) -> set[str]:
    result: set[str] = set()
    for key in keys:
        value = record.get(key)
        entries = value if isinstance(value, list) else [value]
        for entry in entries:
            uid, _ = _member(entry, versioned=key == "memVerList")
            if uid:
                result.add(uid)
    return result


def complete_group_members(
    info: Any, thread_id: str
) -> Optional[list[dict[str, Any]]]:
    """Return a validated complete snapshot, or None when the response is partial.

    A caller may safely replace durable state only when a list is returned. Empty,
    paginated, malformed, and count-mismatched provider responses are rejected.
    """
    record = group_record(info, thread_id)
    if not record or bool(record.get("hasMoreMember")):
        return None

    try:
        expected = int(record.get("totalMember") or 0)
    except (TypeError, ValueError):
        return None
    if expected <= 0:
        return None

    entries: list[Any] = []
    versioned = False
    for key in ("memberIds", "currentMems", "memVerList"):
        value = record.get(key)
        if isinstance(value, list) and value:
            entries = value
            versioned = key == "memVerList"
            break
    if not entries:
        return None

    creator = _identity_set(
        record, ("creatorId", "creator", "ownerId", "owner", "adminId")
    )
    admins = _identity_set(record, ("adminIds", "admins"))
    members: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        uid, metadata = _member(entry, versioned=versioned)
        if not uid or uid in seen:
            continue
        seen.add(uid)
        role = "owner" if uid in creator else "admin" if uid in admins else "member"
        members.append(
            {"zalo_user_id": uid, "role": role, "raw_metadata": metadata}
        )

    if len(members) != expected:
        return None
    return members
