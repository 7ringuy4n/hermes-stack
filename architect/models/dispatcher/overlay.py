# -*- coding: utf-8 -*-
"""Draw short fact lines onto an existing image (weather, fuel, labels)."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from fonts import pillow_font

MAX_OVERLAY_LINES = 6
MIN_FONT = 12
MAX_BAR_RATIO = 0.45


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return pillow_font(size, bold=True)


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
    """Split on spaces so each line's pixel width is <= max_w. Layout only, not NLU."""
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


def layout_overlay_lines(
    facts: Sequence[str],
    *,
    width: int,
    height: int,
    draw: ImageDraw.ImageDraw,
) -> tuple[ImageFont.ImageFont, int, list[tuple[str, int]]]:
    """Return font, bar height, and (line, line_height) that fit inside the image."""
    pad = max(12, width // 40)
    max_w = max(32, width - pad * 2)
    max_bar = max(48, int(height * MAX_BAR_RATIO))
    font_size = max(MIN_FONT, min(36, width // 22))
    fitted: list[tuple[str, int]] = []
    font = _font(font_size)
    bar_h = pad * 2
    for _ in range(16):
        font = _font(font_size)
        gap = max(4, font_size // 5)
        wrapped: list[str] = []
        for fact in facts:
            wrapped.extend(wrap_text_to_width(fact, font, max_w, draw))
        rows: list[tuple[str, int]] = []
        total = pad * 2
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=font)
            th = max(1, bbox[3] - bbox[1])
            tw = bbox[2] - bbox[0]
            if tw > max_w:
                break
            rows.append((line, th))
            total += th
        if rows:
            total += gap * (len(rows) - 1)
        fits = bool(rows) and total <= max_bar and all(
            draw.textbbox((0, 0), t, font=font)[2] - draw.textbbox((0, 0), t, font=font)[0] <= max_w
            for t, _ in rows
        )
        if fits or font_size <= MIN_FONT:
            fitted = rows
            bar_h = min(total if rows else pad * 2, max_bar, height)
            break
        font_size = max(MIN_FONT, font_size - 2)
    while fitted and bar_h > height:
        fitted = fitted[:-1]
        gap = max(4, font_size // 5)
        bar_h = pad * 2 + sum(th for _, th in fitted) + gap * max(0, len(fitted) - 1)
    return font, max(pad * 2, bar_h), fitted


def apply_overlay(path: Path, lines: Sequence[str]) -> None:
    """Paint a bottom bar with the given lines onto path (jpeg/png). Text stays inside the frame."""
    facts = clean_overlay_lines(lines)
    if not facts:
        return
    im = Image.open(path).convert("RGB")
    w, h = im.size
    measure = ImageDraw.Draw(im)
    font, bar_h, rows = layout_overlay_lines(facts, width=w, height=h, draw=measure)
    if not rows:
        return
    pad = max(12, w // 40)
    gap = max(4, getattr(font, "size", 18) // 5)
    y0 = h - bar_h
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, y0, w, h), fill=(0, 0, 0, 165))
    composed = Image.alpha_composite(im.convert("RGBA"), overlay)
    draw2 = ImageDraw.Draw(composed)
    y = y0 + pad
    fill = (255, 255, 255, 255)
    for t, th in rows:
        if y + th > h - 2:
            break
        draw2.text((pad, y), t, fill=fill, font=font)
        y += th + gap
    out = composed.convert("RGB")
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        out.save(path, quality=90)
    else:
        out.save(path)
    try:
        path.chmod(0o664)
    except OSError:
        pass
