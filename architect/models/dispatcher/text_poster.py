# -*- coding: utf-8 -*-
"""Render exact text posters (N copies of a phrase). Do not use diffusion for this."""
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
)

_POSTER_HINT = re.compile(
    r"điền|dien vao|fill\s+(in|with)|write|chữ|chu |poster|dòng|dong |"
    r"\blines?\b|hàng chữ|in chữ|text on",
    re.I,
)
_BW = re.compile(
    r"trắng\s*đen|đen\s*trắng|trang den|black\s*and\s*white|\bb/?w\b|"
    r"grayscale|grey\s*scale|monochrome",
    re.I,
)
_N_LINES = re.compile(r"(\d+)\s*(?:dòng|dong|lines?|hàng)", re.I)
_QUOTED = re.compile(r"[\"“”«»']([^\"“”«»']{1,80})[\"“”«»']")


def parse_text_poster(prompt: str) -> Optional[dict[str, Any]]:
    """If the user wants exact glyphs (N lines of a phrase), return spec; else None."""
    text = (prompt or "").strip()
    if not text:
        return None
    quoted = _QUOTED.findall(text)
    n_m = _N_LINES.search(text)
    hint = bool(_POSTER_HINT.search(text))
    if not quoted and not (hint and n_m):
        return None
    if not hint and not n_m:
        return None
    phrase = (quoted[-1] if quoted else "").strip()
    if not phrase and n_m:
        # "10 dòng KHÁT QUÁ" without quotes
        after = text[n_m.end() :].strip(" :,-")
        after = _QUOTED.sub("", after).strip()
        after = re.sub(r"^(với|with|of|là)\s+", "", after, flags=re.I).strip()
        phrase = after[:80] if after else ""
    if not phrase:
        return None
    n = int(n_m.group(1)) if n_m else 1
    n = max(1, min(n, 80))
    return {
        "phrase": phrase,
        "n": n,
        "bw": bool(_BW.search(text)),
        "raw": text,
    }


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in _FONTS:
        if Path(p).is_file():
            try:
                return ImageFont.truetype(p, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


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
