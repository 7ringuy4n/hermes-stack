# -*- coding: utf-8 -*-
"""Pillow info/weather cards with Vietnamese-safe fonts (no diffusion text)."""
from __future__ import annotations

from io import BytesIO
from typing import Any, Sequence

from PIL import Image, ImageDraw

from fonts import pillow_font

# Style presets — keep drawing vector/icons; text always via pillow_font.
_STYLES = {
    "midnight": {
        "bg": (12, 24, 48),
        "card": (22, 40, 72),
        "card_alt": (28, 50, 88),
        "accent": (56, 132, 220),
        "text": (248, 250, 252),
        "muted": (160, 180, 210),
        "sun": (255, 200, 60),
        "cloud": (210, 220, 235),
    },
    "daylight": {
        "bg": (236, 244, 252),
        "card": (255, 255, 255),
        "card_alt": (245, 250, 255),
        "accent": (30, 120, 200),
        "text": (20, 35, 55),
        "muted": (90, 110, 140),
        "sun": (255, 180, 40),
        "cloud": (150, 170, 190),
    },
    "emerald": {
        "bg": (8, 36, 32),
        "card": (16, 56, 48),
        "card_alt": (22, 70, 60),
        "accent": (40, 180, 140),
        "text": (240, 252, 248),
        "muted": (150, 200, 180),
        "sun": (255, 210, 80),
        "cloud": (180, 210, 200),
    },
}


def parse_info_card_body(prompt: str) -> dict[str, Any]:
    """Parse TITLE/SUBTITLE/ICON/STYLE + fact lines (Hermes-authored markers)."""
    title = ""
    subtitle = ""
    icon = "sun"
    style = "midnight"
    facts: list[str] = []
    for raw in (prompt or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line
        if low.startswith(("TITLE:", "Title:", "title:")):
            title = line.split(":", 1)[1].strip()
            continue
        if low.startswith(("SUBTITLE:", "Subtitle:", "subtitle:")):
            subtitle = line.split(":", 1)[1].strip()
            continue
        if low.startswith(("ICON:", "Icon:", "icon:")):
            icon = line.split(":", 1)[1].strip().split()[0].lower() or "sun"
            continue
        if low.startswith(("STYLE:", "Style:", "style:")):
            style = line.split(":", 1)[1].strip().split()[0].lower() or "midnight"
            continue
        if line.startswith(("- ", "• ", "* ")):
            facts.append(line[2:].strip())
        else:
            facts.append(line)
    if not title and facts:
        title = facts.pop(0)
    if style not in _STYLES:
        style = "midnight"
    return {
        "title": title or "Report",
        "subtitle": subtitle,
        "icon": icon,
        "style": style,
        "facts": facts,
    }


def _round_rect(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], r: int, fill) -> None:
    draw.rounded_rectangle(xy, radius=r, fill=fill)


def _draw_icon(draw: ImageDraw.ImageDraw, icon: str, cx: int, cy: int, pal: dict, scale: float = 1.0) -> None:
    import math

    r = int(40 * scale)
    kind = (icon or "sun").lower()
    if kind in {"rain", "storm"}:
        draw.ellipse((cx - 34, cy - 8, cx + 10, cy + 28), fill=pal["cloud"])
        draw.ellipse((cx - 10, cy - 22, cx + 38, cy + 22), fill=pal["cloud"])
        draw.ellipse((cx - 22, cy - 4, cx + 22, cy + 32), fill=pal["cloud"])
        for i in range(5):
            x = cx - 22 + i * 12
            draw.line((x, cy + 28, x - 5, cy + 48), fill=pal["accent"], width=4)
        if kind == "storm":
            draw.polygon(
                [(cx + 6, cy + 10), (cx - 4, cy + 28), (cx + 8, cy + 28), (cx - 2, cy + 48)],
                fill=pal["sun"],
            )
        return
    if kind in {"cloud", "cloudy"}:
        draw.ellipse((cx - 36, cy - 4, cx + 8, cy + 32), fill=pal["cloud"])
        draw.ellipse((cx - 8, cy - 22, cx + 40, cy + 24), fill=pal["cloud"])
        draw.ellipse((cx - 24, cy + 2, cx + 24, cy + 36), fill=pal["cloud"])
        # soft sun peek
        draw.ellipse((cx + 18, cy - 28, cx + 48, cy + 2), fill=pal["sun"])
        return
    # sun
    draw.ellipse(
        (cx - int(r * 0.5), cy - int(r * 0.5), cx + int(r * 0.5), cy + int(r * 0.5)),
        fill=pal["sun"],
    )
    for i in range(12):
        ang = i * math.pi / 6
        draw.line(
            (
                cx + int(math.cos(ang) * r * 0.72),
                cy + int(math.sin(ang) * r * 0.72),
                cx + int(math.cos(ang) * r * 1.25),
                cy + int(math.sin(ang) * r * 1.25),
            ),
            fill=pal["sun"],
            width=4,
        )


def render_info_card_bytes(
    prompt: str,
    *,
    width: int = 1080,
    height: int = 1350,
    style: str = "",
) -> bytes:
    meta = parse_info_card_body(prompt)
    if style and style in _STYLES:
        meta["style"] = style
    pal = _STYLES[meta["style"]]
    im = Image.new("RGB", (width, height), pal["bg"])
    draw = ImageDraw.Draw(im)

    margin = max(28, width // 36)
    landscape = width >= height
    header_h = 200 if landscape else 280
    # Header card
    _round_rect(draw, (margin, margin, width - margin, margin + header_h), 28, pal["card"])
    _draw_icon(draw, meta["icon"], width - (110 if landscape else 140), margin + header_h // 2, pal, scale=1.15 if landscape else 1.4)
    title_font = pillow_font(36 if landscape else 42, bold=True)
    sub_font = pillow_font(20 if landscape else 22, bold=False)
    draw.text((margin + 36, margin + 48), meta["title"][:48], fill=pal["text"], font=title_font)
    if meta["subtitle"]:
        draw.text((margin + 36, margin + 110), meta["subtitle"][:64], fill=pal["muted"], font=sub_font)

    # Fact grid
    facts = meta["facts"] or ["(no details)"]
    top = margin + header_h + 24
    gap = 16 if landscape else 20
    cols = 4 if landscape else 2
    col_w = (width - 2 * margin - gap * (cols - 1)) // cols
    row_h = 110 if landscape else 150
    max_facts = 8 if landscape else 8
    for i, fact in enumerate(facts[:max_facts]):
        col = i % cols
        row = i // cols
        x0 = margin + col * (col_w + gap)
        y0 = top + row * (row_h + gap)
        if y0 + row_h > height - margin - 40:
            break
        fill = pal["card"] if (row + col) % 2 == 0 else pal["card_alt"]
        _round_rect(draw, (x0, y0, x0 + col_w, y0 + row_h), 18, fill)
        # mini weather glyph by fact text
        kind = _fact_glyph_kind(fact)
        _draw_mini_glyph(draw, kind, x0 + 28, y0 + 36, pal)
        ff = pillow_font(22 if landscape else 26, bold=False)
        text = fact[:70]
        draw.text((x0 + 56, y0 + 48), text, fill=pal["text"], font=ff)

    # Footer bar
    _round_rect(draw, (margin, height - 72, width - margin, height - margin), 14, pal["card"])
    foot = pillow_font(16, bold=False)
    draw.text((margin + 24, height - 56), "Bản tin trực quan · Unicode", fill=pal["muted"], font=foot)

    buf = BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _fact_glyph_kind(fact: str) -> str:
    low = (fact or "").lower()
    if any(x in low for x in ("nhiệt", "temp", "feels", "cảm giác")):
        return "temp"
    if any(x in low for x in ("ẩm", "humid")):
        return "humidity"
    if any(x in low for x in ("gió", "wind")):
        return "wind"
    if any(x in low for x in ("uv", "tím ngoại")):
        return "uv"
    if any(x in low for x in ("mưa", "rain", "precip")):
        return "rain"
    if any(x in low for x in ("mây", "cloud", "tình trạng", "condition")):
        return "cloud"
    return "sun"


def _draw_mini_glyph(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, pal: dict) -> None:
    k = (kind or "sun").lower()
    if k == "humidity":
        draw.ellipse((cx - 8, cy - 4, cx + 8, cy + 12), fill=pal["accent"])
        draw.polygon([(cx, cy - 14), (cx - 9, cy), (cx + 9, cy)], fill=pal["accent"])
        return
    if k == "wind":
        draw.arc((cx - 14, cy - 10, cx + 14, cy + 10), 200, 340, fill=pal["accent"], width=3)
        draw.arc((cx - 10, cy - 2, cx + 16, cy + 12), 200, 340, fill=pal["muted"], width=3)
        return
    if k == "temp":
        draw.rounded_rectangle((cx - 5, cy - 16, cx + 5, cy + 6), radius=4, fill=pal["accent"])
        draw.ellipse((cx - 9, cy + 2, cx + 9, cy + 18), fill=pal["sun"])
        return
    if k == "uv":
        draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=pal["sun"])
        return
    if k == "rain":
        draw.ellipse((cx - 12, cy - 10, cx + 10, cy + 8), fill=pal["cloud"])
        draw.line((cx - 4, cy + 10, cx - 8, cy + 20), fill=pal["accent"], width=3)
        draw.line((cx + 4, cy + 10, cx, cy + 20), fill=pal["accent"], width=3)
        return
    if k == "cloud":
        draw.ellipse((cx - 14, cy - 4, cx + 6, cy + 12), fill=pal["cloud"])
        draw.ellipse((cx - 4, cy - 10, cx + 14, cy + 8), fill=pal["cloud"])
        return
    draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=pal["sun"])


def render_weather_banner_bytes(prompt: str, *, style: str = "daylight") -> bytes:
    """Wide banner for embedding inside styled weather PDFs."""
    return render_info_card_bytes(prompt, width=1200, height=520, style=style or "daylight")


def render_info_card_variants(prompt: str) -> list[tuple[str, bytes]]:
    """Render the same content in each style (local smoke / QA)."""
    out: list[tuple[str, bytes]] = []
    for name in _STYLES:
        out.append((name, render_info_card_bytes(prompt, style=name)))
    return out
