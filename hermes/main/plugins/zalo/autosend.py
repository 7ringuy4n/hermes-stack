"""Autosend window for Zalo compound turns (pure helpers, no I/O)."""
from __future__ import annotations

from pathlib import Path

DEFAULT_GRACE_S = 8.0
# File suffixes are protocol, not user NLU.
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
VIDEO_EXTS = (".mp4", ".webm", ".mov", ".m4v", ".mkv")
ZALO_VIDEO_SUFFIX = ".zalo.mp4"
# Zalo rejects a whitespace-only caption on document attachments
# ("Tham số không hợp lệ"). Omit the caption instead of padding it.
ATTACH_CAPTION_FALLBACK = ""


def _bridge_catalog() -> dict:
    from json import loads
    path = Path(__file__).resolve().parents[2] / "messages" / "zalo-bridge.json"
    try:
        data = loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


def file_in_send_window(
    mtime: float,
    part_t0: float,
    seq_t0: float = 0.0,
    *,
    grace_s: float = DEFAULT_GRACE_S,
    ceiling: float = 0.0,
) -> bool:
    """True if this file belongs to the current part or compound sequence.

    Compound parts each reset part_t0. An image written at the end of part 2
    would look "old" on part 3 if we only compared to part_t0. seq_t0 is the
    first part's start so later parts can still attach an unsent file.

    ceiling: isolated lịch jobs set this when the job ends so a leftover watch
    cannot claim a later job's file.
    """
    try:
        mt = float(mtime)
    except (TypeError, ValueError):
        return False
    grace = max(0.0, float(grace_s))
    floors: list[float] = []
    try:
        p0 = float(part_t0 or 0.0)
    except (TypeError, ValueError):
        p0 = 0.0
    try:
        s0 = float(seq_t0 or 0.0)
    except (TypeError, ValueError):
        s0 = 0.0
    if p0 > 0:
        floors.append(p0)
    if s0 > 0:
        floors.append(s0)
    if not floors:
        in_window = True
    else:
        floor = min(floors) - grace
        in_window = mt + 1.0 >= floor
    if not in_window:
        return False
    try:
        cap = float(ceiling or 0.0)
    except (TypeError, ValueError):
        cap = 0.0
    if cap > 0 and mt > cap + 1.0:
        return False
    return True


def file_ready_for_send(mtime: float, now: float, *, min_age_s: float = 0.8) -> bool:
    """False while the encoder is still writing (mtime too fresh)."""
    try:
        mt = float(mtime)
        t = float(now)
    except (TypeError, ValueError):
        return False
    return (t - mt) >= max(0.0, float(min_age_s))


def looks_invalid_param(err: str) -> bool:
    low = (err or "").lower()
    needles = _bridge_catalog().get("invalid_param_errors") or ()
    return any(str(n).lower() in low for n in needles if str(n).strip())


def looks_retryable_send(err: str) -> bool:
    low = (err or "").lower()
    needles = _bridge_catalog().get("retryable_errors") or ()
    return any(str(n).lower() in low for n in needles if str(n).strip())


def bridge_response_ok(data) -> bool:
    """True when hermes-zalo-plugin JSON means the file/text actually went out."""
    if not isinstance(data, dict):
        return False
    err = data.get("error")
    if err not in (None, "", False):
        return False
    if data.get("success") is False or data.get("ok") is False:
        return False
    if "success" in data:
        return data.get("success") is True
    if "ok" in data:
        return data.get("ok") is True
    return False


def video_dedupe_stem(path: str) -> str:
    """foo.mp4 and foo.zalo.mp4 share one send key."""
    name = Path(str(path or "")).name.lower()
    if name.endswith(ZALO_VIDEO_SUFFIX):
        return name[: -len(ZALO_VIDEO_SUFFIX)]
    p = Path(str(path or ""))
    if p.suffix.lower() in VIDEO_EXTS:
        return (p.stem or p.name or "").lower()
    return (p.stem or p.name or "").lower()


def prefer_remuxed_video(path: str) -> str:
    """Send baseline remux when it exists; otherwise keep the original path."""
    raw = str(path or "").strip()
    if not raw:
        return ""
    p = Path(raw)
    if p.suffix.lower() not in VIDEO_EXTS:
        return raw
    if p.name.endswith(ZALO_VIDEO_SUFFIX):
        return raw
    sibling = p.with_name(p.stem + ZALO_VIDEO_SUFFIX)
    try:
        if sibling.is_file() and sibling.stat().st_size > 1000:
            return str(sibling)
    except OSError:
        return raw
    return raw


def existing_media_path(path: str) -> str:
    """Return path if it exists, else a same-stem image sibling (png/jpg)."""
    raw = str(path or "").strip()
    if not raw:
        return ""
    p = Path(raw)
    try:
        if p.is_file():
            return str(p)
    except OSError:
        return ""
    if p.suffix.lower() not in IMAGE_EXTS:
        return ""
    for ext in IMAGE_EXTS:
        q = p.with_suffix(ext)
        try:
            if q.is_file():
                return str(q)
        except OSError:
            continue
    return ""
