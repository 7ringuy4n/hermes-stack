# -*- coding: utf-8 -*-
"""Draw short fact lines onto an existing image (weather badge, labels)."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from fonts import pillow_font

MAX_OVERLAY_LINES = 6
MIN_FONT = 13
MAX_BOX_RATIO = 0.38


def _font(size: int, *, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return pillow_font(size, bold=bold)


def clean_overlay_lines(lines: Sequence[str] | None, *, limit: int = MAX_OVERLAY_LINES) -> list[str]:
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


def wrap_text_to_width(text: str, font: ImageFont.ImageFont, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Split on spaces so each line's pixel width is <= max_w."""
    raw = " ".join(str(text or "").split())
    if not raw or max_w <= 0:
        return [raw] if raw else []
    words = raw.split(" ")
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = word if not cur else f"{cur} {word}"
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        bbox_w = draw.textbbox((0, 0), word, font=font)
        if bbox_w[2] - bbox_w[0] <= max_w:
            cur = word
            continue
        chunk = ""
        for ch in word:
            nxt = chunk + ch
            cb = draw.textbbox((0, 0), nxt, font=font)
            if chunk and cb[2] - cb[0] > max_w:
                lines.append(chunk)
                chunk = ch
            else:
                chunk = nxt
        cur = chunk
    if cur:
        lines.append(cur)
    return lines or [raw]


def _layout_box(
    facts: Sequence[str],
    *,
    width: int,
    height: int,
    draw: ImageDraw.ImageDraw,
    max_box_w: int,
) -> tuple[ImageFont.ImageFont, int, int, list[tuple[str, int]]]:
    """Return font, box_w, box_h, and (line, line_height) for a compact badge."""
    pad = max(10, width // 48)
    inner_max_w = max(32, max_box_w - pad * 2)
    max_box_h = max(48, int(height * MAX_BOX_RATIO))
    font_size = max(MIN_FONT, min(28, width // 28))
    fitted: list[tuple[str, int]] = []
    font = _font(font_size)
    box_w = pad * 2
    box_h = pad * 2
    for _ in range(14):
        font = _font(font_size)
        gap = max(3, font_size // 6)
        wrapped: list[str] = []
        for fact in facts:
            wrapped.extend(wrap_text_to_width(fact, font, inner_max_w, draw))
        rows: list[tuple[str, int]] = []
        total_h = pad * 2
        max_line_w = 0
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=font)
            th = max(1, bbox[3] - bbox[1])
            tw = bbox[2] - bbox[0]
            if tw > inner_max_w:
                break
            rows.append((line, th))
            max_line_w = max(max_line_w, tw)
            total_h += th
        if rows:
            total_h += gap * (len(rows) - 1)
        box_w = min(max_box_w, max(pad * 2, max_line_w + pad * 2))
        fits = bool(rows) and total_h <= max_box_h
        if fits or font_size <= MIN_FONT:
            fitted = rows
            box_h = min(total_h if rows else pad * 2, max_box_h, height)
            break
        font_size = max(MIN_FONT, font_size - 1)
    return font, box_w, box_h, fitted


def apply_overlay(path: Path, lines: Sequence[str], *, corner: str = "bottom-left") -> None:
    """Paint fact lines onto path. Default: compact badge at bottom-left."""
    facts = clean_overlay_lines(lines)
    if not facts:
        return
    im = Image.open(path).convert("RGB")
    w, h = im.size
    measure = ImageDraw.Draw(im)
    max_box_w = max(120, int(w * 0.42))
    font, box_w, box_h, rows = _layout_box(
        facts, width=w, height=h, draw=measure, max_box_w=max_box_w
    )
    if not rows:
        return
    pad = max(10, w // 48)
    gap = max(3, getattr(font, "size", 18) // 6)
    margin = max(12, w // 40)
    corner_key = (corner or "bottom-left").strip().lower()
    if corner_key in {"bottom", "bottom-bar"}:
        x0, y0 = 0, h - box_h
        box_w = w
    else:
        x0 = margin
        y0 = h - box_h - margin
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        (x0, y0, x0 + box_w, y0 + box_h),
        radius=max(8, min(18, box_w // 12)),
        fill=(8, 16, 28, 200),
    )
    composed = Image.alpha_composite(im.convert("RGBA"), overlay)
    draw2 = ImageDraw.Draw(composed)
    y = y0 + pad
    fill = (248, 252, 255, 255)
    accent = (120, 210, 255, 255)
    for i, (t, th) in enumerate(rows):
        if y + th > y0 + box_h - 2:
            break
        line_fill = accent if i == 0 else fill
        draw2.text((x0 + pad, y), t, fill=line_fill, font=font)
        y += th + gap
    out = composed.convert("RGB")
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        out.save(path, quality=92)
    else:
        out.save(path)
    try:
        path.chmod(0o664)
    except OSError:
        pass
