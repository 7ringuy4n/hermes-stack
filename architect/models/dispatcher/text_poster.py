# -*- coding: utf-8 -*-
"""Render exact text posters (N copies of a phrase). Do not use diffusion for this."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

from fonts import pillow_font


def parse_text_poster(
    prompt: str = "",
    *,
    phrase: str = "",
    n: int | None = None,
    bw: bool | None = None,
) -> Optional[dict[str, Any]]:
    """Build a poster spec from classify JSON fields. Does not scan user prose."""
    text = (phrase or "").strip() or (prompt or "").strip()
    if not text:
        return None
    if n is None and not phrase:
        return None
    count = 1 if n is None else int(n)
    count = max(1, min(count, 80))
    return {
        "phrase": text[:80],
        "n": count,
        "bw": bool(bw) if bw is not None else True,
        "raw": prompt or text,
    }


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return pillow_font(size, bold=True)


def render_text_poster_bytes(spec: dict[str, Any], *, width: int = 1080, height: int = 1350) -> bytes:
    """High-contrast readable poster: N identical lines of the exact phrase."""
    phrase = spec["phrase"]
    n = int(spec["n"])
    bw = bool(spec.get("bw"))
    bg = (255, 255, 255) if bw else (255, 255, 255)
    fg = (0, 0, 0)
    im = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(im)
    margin = 64
    usable_h = height - 2 * margin
    line_h = max(28, usable_h // max(n, 1))
    font_size = min(120, max(22, int(line_h * 0.72)))
    font = _font(font_size)
    # Shrink font until the phrase fits width
    for _ in range(12):
        bbox = draw.textbbox((0, 0), phrase, font=font)
        tw = bbox[2] - bbox[0]
        if tw <= width - 2 * margin:
            break
        font_size = max(16, int(font_size * 0.88))
        font = _font(font_size)
    bbox = draw.textbbox((0, 0), phrase, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    gap = (usable_h - n * th) / max(n + 1, 1)
    y = margin + gap
    for _ in range(n):
        x = (width - tw) // 2
        draw.text((x, y), phrase, fill=fg, font=font)
        y += th + gap
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()
