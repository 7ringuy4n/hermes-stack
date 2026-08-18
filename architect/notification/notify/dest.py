"""Resolve the Zalo inbox for admin alerts.

Order: request thread → NOTIFY_ZALO_THREAD (override) → sole admin file → ZALO_ADMIN_USERS env.
Re-read the admin file on each call so !zalo claim / transfer take effect without restart.
Never log the uid.
"""
from __future__ import annotations

import os

SRC_REQUEST = "request"
SRC_OVERRIDE = "override"
SRC_ADMIN_FILE = "admin_file"
SRC_ADMIN_ENV = "admin_env"
SRC_NONE = "none"


def parse_admin_file(text: str) -> str:
    """First non-comment line: `uid` or `uid | name`."""
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        uid = raw.split("|", 1)[0].strip()
        if uid:
            return uid
    return ""


def parse_admin_env(raw: str) -> str:
    """Bootstrap env: first comma-separated id only (sole admin)."""
    for part in (raw or "").split(","):
        uid = part.strip()
        if uid:
            return uid
    return ""


def read_admin_file(path: str) -> str:
    p = (path or "").strip()
    if not p or not os.path.isfile(p):
        return ""
    try:
        with open(p, encoding="utf-8") as f:
            return parse_admin_file(f.read())
    except OSError:
        return ""


def resolve_zalo_dest(
    *,
    request_thread: str = "",
    env_thread: str = "",
    file_text: str = "",
    env_admins: str = "",
) -> tuple[str, str]:
    """Return (thread_id, source). Empty id → source none."""
    tid = (request_thread or "").strip()
    if tid:
        return tid, SRC_REQUEST
    tid = (env_thread or "").strip()
    if tid:
        return tid, SRC_OVERRIDE
    tid = parse_admin_file(file_text)
    if tid:
        return tid, SRC_ADMIN_FILE
    tid = parse_admin_env(env_admins)
    if tid:
        return tid, SRC_ADMIN_ENV
    return "", SRC_NONE


def resolve_zalo_dest_live(
    *,
    request_thread: str = "",
    env_thread: str = "",
    admin_file: str = "",
    env_admins: str = "",
) -> tuple[str, str]:
    """Same as resolve_zalo_dest, reading the admin file from disk."""
    return resolve_zalo_dest(
        request_thread=request_thread,
        env_thread=env_thread,
        file_text=read_admin_file(admin_file),
        env_admins=env_admins,
    )
