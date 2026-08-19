# -*- coding: utf-8 -*-
"""Draw short fact lines onto an existing image (weather, fuel, labels)."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in _FONTS:
        if Path(p).is_file():
            try:
                return ImageFont.truetype(p, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def clean_overlay_lines(lines: Sequence[str] | None, *, limit: int = 6) -> list[str]:
    """Keep short non-empty lines. Caller supplies facts; this does not parse prose."""
    out: list[str] = []
    for raw in lines or []:
        t = " ".join(str(raw or "").split())
        if not t:
            continue
        out.append(t[:120])
        if len(out) >= limit:
            break
    return out


def apply_overlay(path: Path, lines: Sequence[str]) -> None:
    """Paint a bottom bar with the given lines onto path (jpeg/png)."""
    facts = clean_overlay_lines(lines)
    if not facts:
        return
    im = Image.open(path).convert("RGB")
    w, h = im.size
    draw = ImageDraw.Draw(im, "RGBA") if False else ImageDraw.Draw(im)
    font_size = max(18, min(36, w // 22))
    font = _font(font_size)
    pad = max(12, w // 40)
    line_gap = max(4, font_size // 5)
    heights: list[int] = []
    for t in facts:
        bbox = draw.textbbox((0, 0), t, font=font)
        heights.append(bbox[3] - bbox[1])
    bar_h = pad * 2 + sum(heights) + line_gap * (len(facts) - 1)
    bar_h = min(bar_h, h // 2)
    y0 = h - bar_h
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, y0, w, h), fill=(0, 0, 0, 165))
    base = im.convert("RGBA")
    composed = Image.alpha_composite(base, overlay)
    draw2 = ImageDraw.Draw(composed)
    y = y0 + pad
    fill = (255, 255, 255, 255)
    for t, th in zip(facts, heights):
        draw2.text((pad, y), t, fill=fill, font=font)
        y += th + line_gap
    out = composed.convert("RGB")
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        out.save(path, quality=90)
    else:
        out.save(path)
