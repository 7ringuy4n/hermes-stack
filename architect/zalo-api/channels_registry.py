"""Message Worker channel registry — durable platform id/name lookup.

Stores social channel metadata (Zalo/Telegram/Lark/…) for later resolution by name or id.
Populated from allowlists, inbound traffic, bridge contacts, and admin label commands.
"""
from __future__ import annotations

import json
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REGISTRY_FILE = Path(
    os.environ.get("CHANNELS_REGISTRY_FILE", "/data/assistant/channels/registry.json")
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm_text(s: str) -> str:
    """Lowercase + strip Vietnamese diacritics for forgiving name search."""
    blob = unicodedata.normalize("NFD", str(s or ""))
    blob = "".join(c for c in blob if unicodedata.category(c) != "Mn")
    return blob.replace("đ", "d").replace("Đ", "D").lower().strip()


def _load() -> dict[str, Any]:
    try:
        if REGISTRY_FILE.is_file():
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("channels"), list):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"channels": [], "updated_at": None}


def _save(data: dict[str, Any]) -> None:
    data["updated_at"] = _now_iso()
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(REGISTRY_FILE, 0o664)
    except OSError:
        pass


def upsert(
    platform: str,
    external_id: str,
    *,
    name: str = "",
    kind: str = "group",
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    plat = (platform or "").strip().lower()
    eid = (external_id or "").strip()
    if not plat or not eid:
        raise ValueError("platform and external_id required")
    data = _load()
    channels: list[dict[str, Any]] = data.setdefault("channels", [])
    row: dict[str, Any] | None = None
    for ch in channels:
        if ch.get("platform") == plat and str(ch.get("external_id") or "") == eid:
            row = ch
            break
    if row is None:
        row = {"platform": plat, "external_id": eid, "kind": kind, "name": "", "meta": {}}
        channels.append(row)
    if name.strip():
        row["name"] = name.strip()
    if kind.strip():
        row["kind"] = kind.strip()
    if meta:
        base = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        base.update(meta)
        row["meta"] = base
    row["updated_at"] = _now_iso()
    _save(data)
    return row


def list_channels(platform: Optional[str] = None) -> list[dict[str, Any]]:
    plat = (platform or "").strip().lower()
    out = []
    for ch in _load().get("channels") or []:
        if not isinstance(ch, dict):
            continue
        if plat and str(ch.get("platform") or "").lower() != plat:
            continue
        out.append(dict(ch))
    return out


_PLATFORM_NAME_PREFIXES = (
    "zalo",
    "telegram",
    "lark",
    "discord",
    "slack",
    "whatsapp",
)


def _ref_variants(ref: str) -> list[str]:
    """Deterministic name variants (strip known platform prefixes)."""
    base = (ref or "").strip()
    if not base:
        return []
    out: list[str] = [base]
    low = base.lower()
    for prefix in _PLATFORM_NAME_PREFIXES:
        token = prefix + " "
        if low.startswith(token):
            stripped = base[len(token) :].strip()
            if stripped and stripped not in out:
                out.append(stripped)
    return out


def resolve(platform: str, ref: str) -> Optional[dict[str, Any]]:
    """Resolve channel by exact id or diacritic-insensitive name match."""
    plat = (platform or "").strip().lower()
    needle = (ref or "").strip()
    if not plat or not needle:
        return None
    channels = list_channels(plat)
    for ch in channels:
        if str(ch.get("external_id") or "") == needle:
            return ch

    def _pick(matches: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            groups = [ch for ch in matches if str(ch.get("kind") or "").lower() in {"group", "g"}]
            if len(groups) == 1:
                return groups[0]
        return None

    for variant in _ref_variants(needle):
        low = variant.lower()
        norm = norm_text(variant)
        exact = [
            ch
            for ch in channels
            if str(ch.get("name") or "").lower() == low
            or norm_text(str(ch.get("name") or "")) == norm
        ]
        hit = _pick(exact)
        if hit:
            return hit
        partial = []
        for ch in channels:
            name = str(ch.get("name") or "")
            name_low = name.lower()
            name_norm = norm_text(name)
            if not name_low:
                continue
            # Either side may contain the other ("Zalo LC group" ↔ "LC group").
            if (
                low in name_low
                or name_low in low
                or (norm and norm in name_norm)
                or (name_norm and name_norm in norm)
            ):
                partial.append(ch)
        hit = _pick(partial)
        if hit:
            return hit
    return None


def sync_from_allowlist(platform: str, entries: list[dict[str, str]], *, kind: str = "group") -> int:
    n = 0
    for e in entries:
        tid = str(e.get("id") or "").strip()
        if not tid:
            continue
        upsert(platform, tid, name=str(e.get("name") or ""), kind=kind)
        n += 1
    return n


def sync_contacts(platform: str, groups: list[dict[str, Any]], friends: list[dict[str, Any]]) -> int:
    """Seed registry from bridge /contacts payload."""
    n = 0
    for g in groups or []:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or g.get("groupId") or "").strip()
        if not gid:
            continue
        upsert(
            platform,
            gid,
            name=str(g.get("name") or g.get("groupName") or ""),
            kind="group",
            meta={"source": "contacts"},
        )
        n += 1
    for f in friends or []:
        if not isinstance(f, dict):
            continue
        uid = str(f.get("id") or f.get("userId") or f.get("uid") or "").strip()
        if not uid:
            continue
        upsert(
            platform,
            uid,
            name=str(f.get("name") or f.get("displayName") or f.get("zaloName") or ""),
            kind="user",
            meta={"source": "contacts"},
        )
        n += 1
    return n
