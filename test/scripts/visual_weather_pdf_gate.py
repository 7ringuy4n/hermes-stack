# -*- coding: utf-8 -*-
"""Pure result parsing shared by the visual-weather PDF live gate and unit."""
from __future__ import annotations

import re


def new_pdf_seen(text: str) -> bool:
    """Require the positive line token; ``NO_NEW_PDF`` must never match."""
    return bool(re.search(r"(?m)^NEW_PDF\s+\S+", text or ""))


def delivered_image_count(text: str) -> int | None:
    """Return the durable delivery count, or None when the audit failed."""
    match = re.search(r"(?m)^DELIVERED_IMAGE_COUNT\s+(\d+)\s*$", text or "")
    return int(match.group(1)) if match else None
