# -*- coding: utf-8 -*-
"""Resolve Zalo inject identity from host allowlist (never commit ids).

- Prefer ``want_name`` when set (develop lab: ``Tn``).
- If that name is missing: first admin (main / any-admin).
- Optional ``want_id`` wins when set.
- Set ``strict_name=True`` to require a named match (develop-only Tn suites).
"""
from __future__ import annotations

from pathlib import Path

RESOLVE_REMOTE_PY = r'''
def resolve_admin_user(want_name="", want_id="", strict_name=False, paths=(
    "/data/assistant/zalo_admin_users.txt",
    "/opt/data/zalo_admin_users.txt",
)):
    want_name = (want_name or "").strip()
    want_id = (want_id or "").strip()
    first = named = None
    for path in paths:
        from pathlib import Path as _P
        p = _P(path)
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            left, _, right = raw.partition("|")
            uid, name = left.strip(), right.strip()
            if not uid:
                continue
            if want_id and uid == want_id:
                return uid, name or "admin"
            if first is None:
                first = (uid, name or "admin")
            if want_name and name.lower() == want_name.lower():
                named = (uid, name)
                break
        if named:
            return named
    if want_id:
        raise RuntimeError("NO_ADMIN_USER id=" + want_id)
    if named:
        return named
    if want_name and strict_name:
        raise RuntimeError("NO_ADMIN_USER name=" + want_name)
    if first:
        return first
    raise RuntimeError("NO_ADMIN_USER")
'''


def resolve_admin_user(
    want_name: str = "",
    *,
    paths: tuple[str, ...] = (
        "/data/assistant/zalo_admin_users.txt",
        "/opt/data/zalo_admin_users.txt",
    ),
    want_id: str = "",
    strict_name: bool = False,
) -> tuple[str, str]:
    """Return (uid, display_name). Raises RuntimeError if none."""
    want_name = (want_name or "").strip()
    want_id = (want_id or "").strip()
    first: tuple[str, str] | None = None
    named: tuple[str, str] | None = None
    for path in paths:
        p = Path(path)
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            left, _, right = raw.partition("|")
            uid = left.strip()
            name = right.strip()
            if not uid:
                continue
            if want_id and uid == want_id:
                return uid, name or "admin"
            if first is None:
                first = (uid, name or "admin")
            if want_name and name.lower() == want_name.lower():
                named = (uid, name)
                break
        if named:
            return named
    if want_id:
        raise RuntimeError(f"NO_ADMIN_USER id={want_id}")
    if named:
        return named
    if want_name and strict_name:
        raise RuntimeError(f"NO_ADMIN_USER name={want_name}")
    if first:
        return first
    raise RuntimeError("NO_ADMIN_USER")
