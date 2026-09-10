"""Feature toggle helpers — active|inactive only."""
from __future__ import annotations

import os


def env_active(name: str, default: str = "inactive") -> bool:
    """True only when env *name* is exactly ``active`` (unset uses *default*)."""
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return (default or "inactive").strip().lower() == "active"
    val = str(raw).strip().lower()
    if val == "active":
        return True
    if val == "inactive":
        return False
    return False


def env_inactive(name: str, default: str = "inactive") -> bool:
    return not env_active(name, default)


def raw_env_active(raw: str | None, *, default: str = "inactive") -> bool:
    if raw is None or not str(raw).strip():
        return (default or "inactive").strip().lower() == "active"
    val = str(raw).strip().lower()
    if val == "active":
        return True
    if val == "inactive":
        return False
    return False
