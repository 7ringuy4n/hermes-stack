"""Shared Unicode font resolution for Dispatcher media (Pillow overlay / posters).

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

_CANDIDATES_INTER_REG = (
    str(_BUNDLE / "Inter-Regular.ttf"),
    "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
    "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
    "C:/Windows/Fonts/Inter-Regular.ttf",
)
_CANDIDATES_INTER_MEDIUM = (
    str(_BUNDLE / "Inter-Medium.ttf"),
    "/usr/share/fonts/truetype/inter/Inter-Medium.ttf",
    "/usr/share/fonts/opentype/inter/Inter-Medium.otf",
    "C:/Windows/Fonts/Inter-Medium.ttf",
)
_CANDIDATES_INTER_BOLD = (
    str(_BUNDLE / "Inter-SemiBold.ttf"),
    str(_BUNDLE / "Inter-Bold.ttf"),
    "/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf",
    "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
    "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "C:/Windows/Fonts/Inter-SemiBold.ttf",
)
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
_CANDIDATES_SERIF_REG = (
    "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "C:/Windows/Fonts/georgia.ttf",
)
_CANDIDATES_SERIF_BOLD = (
    "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "C:/Windows/Fonts/georgiab.ttf",
)
_CANDIDATES_MONO_REG = (
    "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/consola.ttf",
)
_CANDIDATES_MONO_BOLD = (
    "/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "C:/Windows/Fonts/consolab.ttf",
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


@lru_cache(maxsize=16)
def resolve_font_path(*, bold: bool = False, weight: str = "", family: str = "auto") -> str:
    """Return absolute TTF path with Vietnamese coverage when possible."""
    normalized_weight = (weight or ("bold" if bold else "regular")).strip().lower()
    wants_bold = normalized_weight in {"medium", "semibold", "bold"}
    normalized_family = (family or "auto").strip().lower()
    inter = _CANDIDATES_INTER_BOLD if wants_bold else _CANDIDATES_INTER_REG
    if normalized_weight == "medium":
        inter = _CANDIDATES_INTER_MEDIUM + _CANDIDATES_INTER_BOLD
    noto = _CANDIDATES_BOLD if wants_bold else _CANDIDATES_REG
    if normalized_family == "serif":
        cands = (_CANDIDATES_SERIF_BOLD if wants_bold else _CANDIDATES_SERIF_REG) + noto
    elif normalized_family == "mono":
        cands = (_CANDIDATES_MONO_BOLD if wants_bold else _CANDIDATES_MONO_REG) + noto
    elif normalized_family in {"auto", "inter"}:
        cands = inter + noto
    else:
        cands = noto
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


@lru_cache(maxsize=128)
def pillow_font(
    size: int, *, bold: bool = False, weight: str = "", family: str = "auto"
) -> Any:
    from PIL import ImageFont

    path = resolve_font_path(bold=bold, weight=weight, family=family)
    try:
        return ImageFont.truetype(path, size=max(8, int(size)))
    except OSError:
        log.error("truetype failed for %s; Vietnamese will break", path)
        return ImageFont.load_default()


def clear_font_caches() -> None:
    resolve_font_path.cache_clear()
    pillow_font.cache_clear()
