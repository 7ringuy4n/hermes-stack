"""Autosend window for Zalo compound turns (pure helpers, no I/O)."""
from __future__ import annotations

DEFAULT_GRACE_S = 8.0


def file_in_send_window(
    mtime: float,
    part_t0: float,
    seq_t0: float = 0.0,
    *,
    grace_s: float = DEFAULT_GRACE_S,
) -> bool:
    """True if this file belongs to the current part or compound sequence.

    Compound parts each reset part_t0. An image written at the end of part 2
    would look "old" on part 3 if we only compared to part_t0. seq_t0 is the
    first part's start so later parts can still attach an unsent file.
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
        return True
    floor = min(floors) - grace
    return mt + 1.0 >= floor
