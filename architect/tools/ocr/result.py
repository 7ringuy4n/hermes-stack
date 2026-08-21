"""OCR response helpers (unit-testable without FastAPI)."""
from __future__ import annotations

from typing import Any


def empty_scan_result(via: str) -> dict[str, Any]:
    """Local OCR finished; the image simply has no readable glyphs."""
    return {"ok": True, "text": "", "via": via or "none", "empty": True}
