# -*- coding: utf-8 -*-
"""Shared Unicode font resolution for Dispatcher media (PDF + Pillow).

Prefer bundled Noto Sans (Vietnamese-complete), then system fonts. Never use the
PIL bitmap default when a TTF is available — that produces tofu for diacritics.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

log = logging.getLogger("fonts")

# Sample must include Vietnamese diacritics that commonly become tofu.
_VI_SAMPLE = "Hồ Chí Minh ữớăâêôƯỢặảấ"

_BUNDLE = Path(__file__).resolve().parent / "fonts"

_CANDIDATES_REG = (
    str(_BUNDLE / "NotoSans-Regular.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/seguisym.ttf",
)
_CANDIDATES_BOLD = (
    str(_BUNDLE / "NotoSans-Bold.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/tahomabd.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _pillow_covers(path: str, sample: str = _VI_SAMPLE) -> bool:
    try:
        from PIL import ImageFont
    except ImportError:
        return Path(path).is_file()
    try:
        font = ImageFont.truetype(path, size=32)
    except OSError:
        return False
    for ch in sample:
        if ord(ch) < 128:
            continue
        try:
            mask = font.getmask(ch)
            if not mask.size[0] or not mask.size[1]:
                return False
        except Exception:  # noqa: BLE001
            return False
    return True


@lru_cache(maxsize=4)
def resolve_font_path(*, bold: bool = False) -> str:
    """Return absolute TTF path with Vietnamese coverage when possible."""
    cands = _CANDIDATES_BOLD if bold else _CANDIDATES_REG
    fallback = ""
    for p in cands:
        if not Path(p).is_file():
            continue
        if not fallback:
            fallback = p
        if _pillow_covers(p):
            return p
    if fallback:
        log.warning("font %s may lack Vietnamese glyphs", fallback)
        return fallback
    raise FileNotFoundError("no TTF font available for media rendering")


@lru_cache(maxsize=64)
def pillow_font(size: int, *, bold: bool = False) -> Any:
    from PIL import ImageFont

    path = resolve_font_path(bold=bold)
    try:
        return ImageFont.truetype(path, size=max(8, int(size)))
    except OSError:
        # Last resort — caller should avoid this path for Vietnamese.
        log.error("truetype failed for %s; Vietnamese will break", path)
        return ImageFont.load_default()


@lru_cache(maxsize=4)
def reportlab_font_name(*, bold: bool = False) -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    name = "MediaSansBold" if bold else "MediaSans"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    path = resolve_font_path(bold=bold)
    pdfmetrics.registerFont(TTFont(name, path))
    return name


def clear_font_caches() -> None:
    resolve_font_path.cache_clear()
    pillow_font.cache_clear()
    reportlab_font_name.cache_clear()
