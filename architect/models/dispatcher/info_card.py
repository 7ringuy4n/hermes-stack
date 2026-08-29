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


def _is_scene_prompt_dump(line: str) -> bool:
    """English diffusion/scene prose mistakenly used as card body (not NLU)."""
    s = (line or "").strip()
    if not s or len(s) < 28:
        return False
    low = s.lower()
    if low.startswith(("title:", "subtitle:", "icon:", "style:", "overview:", "background:")):
        return False
    if ":" in s and len(s.split(":", 1)[0]) <= 24:
        # labeled fact
        return False
    needles = (
        "info card for",
        "weather info card",
        "modern ui",
        "modern g",
        "infographic of",
        "generate an image",
        "create an image",
        "beautiful weather",
    )
    return any(n in low for n in needles) or (len(s) > 70 and " for " in low and "city" in low)


def parse_info_card_body(prompt: str) -> dict[str, Any]:
    """Parse TITLE/SUBTITLE/ICON/STYLE/OVERVIEW/BACKGROUND + fact lines (Hermes markers)."""
    title = ""
    subtitle = ""
    icon = "sun"
    style = "midnight"
    overview = ""
    background = ""
    facts: list[str] = []
    for raw in (prompt or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if _is_scene_prompt_dump(line):
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
        if low.startswith(("OVERVIEW:", "Overview:", "overview:")):
            overview = line.split(":", 1)[1].strip()
            continue
        if low.startswith(("BACKGROUND:", "Background:", "background:")):
            background = line.split(":", 1)[1].strip()
            continue
        if line.startswith(("- ", "• ", "* ")):
            facts.append(line[2:].strip())
        else:
            facts.append(line)
    # Never promote a scene-prompt dump to TITLE
    if title and _is_scene_prompt_dump(f"x {title}"):
        title = ""
    if not title:
        title = "Thông tin cập nhật"
    if style not in _STYLES:
        style = "midnight"
    # Drop empty / placeholder facts
    clean_facts: list[str] = []
    for f in facts:
        s = (f or "").strip()
        if not s or s.lower() in {"(no details)", "no details", "n/a"}:
            continue
        if _is_scene_prompt_dump(s):
            continue
        clean_facts.append(s)
    return {
        "title": title,
        "subtitle": subtitle,
        "icon": icon,
        "style": style,
        "overview": overview,
        "background": background,
        "facts": clean_facts,
    }


def _round_rect(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], r: int, fill) -> None:
    draw.rounded_rectangle(xy, radius=r, fill=fill)


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: Any,
    max_width: int,
    max_lines: int = 3,
) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                return lines
    if len(lines) < max_lines:
        lines.append(cur)
    return lines[:max_lines]


def _draw_icon(draw: ImageDraw.ImageDraw, icon: str, cx: int, cy: int, pal: dict, scale: float = 1.0) -> None:
    import math

    r = int(40 * scale)
    kind = (icon or "sun").lower()
    if kind in {"rain", "storm", "mưa", "mua"}:
        draw.ellipse((cx - 34, cy - 8, cx + 10, cy + 28), fill=pal["cloud"])
        draw.ellipse((cx - 10, cy - 22, cx + 38, cy + 22), fill=pal["cloud"])
        draw.ellipse((cx - 22, cy - 4, cx + 22, cy + 32), fill=pal["cloud"])
        for i in range(5):
            x = cx - 22 + i * 12
            draw.line((x, cy + 28, x - 5, cy + 48), fill=pal["accent"], width=4)
        if kind in {"storm"}:
            draw.polygon(
                [(cx + 6, cy + 10), (cx - 4, cy + 28), (cx + 8, cy + 28), (cx - 2, cy + 48)],
                fill=pal["sun"],
            )
        return
    if kind in {"cloud", "cloudy", "mây"}:
        draw.ellipse((cx - 36, cy - 4, cx + 8, cy + 32), fill=pal["cloud"])
        draw.ellipse((cx - 8, cy - 22, cx + 40, cy + 24), fill=pal["cloud"])
        draw.ellipse((cx - 24, cy + 2, cx + 24, cy + 36), fill=pal["cloud"])
        draw.ellipse((cx + 18, cy - 28, cx + 48, cy + 2), fill=pal["sun"])
        return
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


def _split_lv(fact: str) -> tuple[str, str]:
    s = (fact or "").strip()
    if ": " in s:
        a, b = s.split(": ", 1)
        if 1 <= len(a) <= 40 and b.strip():
            return a.strip(), b.strip()
    if ":" in s and s.index(":") < 40:
        a, b = s.split(":", 1)
        if b.strip():
            return a.strip(), b.strip()
    return "", s


def _hero_temp(facts: list[str]) -> str:
    for fact in facts:
        label, value = _split_lv(fact)
        low = label.lower()
        if any(x in low for x in ("nhiệt", "temp", "feels", "cảm giác")):
            for token in value.replace(",", " ").split():
                t = token.strip().strip(".,;")
                if t.endswith(("°C", "ºC")) or "℃" in t:
                    return t
                if t.replace(".", "", 1).isdigit():
                    return f"{t}°C"
    return ""


def render_info_card_bytes(
    prompt: str,
    *,
    width: int = 1080,
    height: int = 1350,
    style: str = "",
    overlay: Sequence[str] | None = None,
) -> bytes:
    meta = parse_info_card_body(prompt)
    if style and style in _STYLES:
        meta["style"] = style
    # Merge overlay fact lines (already-fetched) into body facts
    extra = [str(x).strip() for x in (overlay or []) if str(x).strip()]
    for line in extra:
        if line.startswith(("- ", "• ", "* ")):
            line = line[2:].strip()
        if line and line not in meta["facts"] and not _is_scene_prompt_dump(line):
            meta["facts"].append(line)

    pal = _STYLES[meta["style"]]
    im = Image.new("RGB", (width, height), pal["bg"])
    draw = ImageDraw.Draw(im)

    margin = max(28, width // 36)
    landscape = width >= height
    has_place = bool(meta.get("overview") or meta.get("background"))
    header_h = 220 if landscape else (360 if has_place else 280)

    _round_rect(draw, (margin, margin, width - margin, margin + header_h), 28, pal["card"])
    _draw_icon(
        draw,
        meta["icon"],
        width - (110 if landscape else 140),
        margin + min(header_h // 2, 160),
        pal,
        scale=1.15 if landscape else 1.4,
    )

    title_font = pillow_font(34 if landscape else 40, bold=True)
    sub_font = pillow_font(20 if landscape else 22, bold=False)
    body_font = pillow_font(20, bold=False)
    label_sm = pillow_font(16, bold=True)
    text_w = width - 2 * margin - 200
    y = margin + 36
    for line in _wrap_lines(draw, meta["title"], title_font, text_w, max_lines=2):
        draw.text((margin + 36, y), line, fill=pal["text"], font=title_font)
        y += 44
    if meta["subtitle"]:
        draw.text((margin + 36, y + 4), meta["subtitle"][:64], fill=pal["muted"], font=sub_font)
        y += 36
    hero = _hero_temp(meta["facts"])
    if hero and not has_place:
        hero_f = pillow_font(64, bold=True)
        draw.text((margin + 36, y + 8), hero, fill=pal["text"], font=hero_f)
        y += 72
    if meta.get("overview"):
        draw.text((margin + 36, y + 4), "Tổng quan", fill=pal["accent"], font=label_sm)
        y += 26
        for line in _wrap_lines(draw, meta["overview"][:180], body_font, text_w, max_lines=3):
            draw.text((margin + 36, y), line, fill=pal["text"], font=body_font)
            y += 26
    if meta.get("background"):
        draw.text((margin + 36, y + 6), "Bối cảnh", fill=pal["accent"], font=label_sm)
        y += 28
        for line in _wrap_lines(draw, meta["background"][:180], body_font, text_w, max_lines=2):
            draw.text((margin + 36, y), line, fill=pal["muted"], font=body_font)
            y += 26

    facts = list(meta["facts"])
    if hero:
        facts = [f for f in facts if _fact_glyph_kind(f) != "temp" or ": " not in f]
    if not facts:
        if meta.get("overview"):
            facts = [meta["overview"][:70]]
        else:
            facts = ["Đang cập nhật chi tiết"]

    top = margin + header_h + 24
    gap = 16 if landscape else 20
    cols = 4 if landscape else 2
    col_w = (width - 2 * margin - gap * (cols - 1)) // cols
    row_h = 120 if landscape else 160
    label_f = pillow_font(18, bold=False)
    value_f = pillow_font(28, bold=True)
    for i, fact in enumerate(facts[:8]):
        col = i % cols
        row = i // cols
        x0 = margin + col * (col_w + gap)
        y0 = top + row * (row_h + gap)
        if y0 + row_h > height - margin - 40:
            break
        fill = pal["card"] if (row + col) % 2 == 0 else pal["card_alt"]
        _round_rect(draw, (x0, y0, x0 + col_w, y0 + row_h), 18, fill)
        kind = _fact_glyph_kind(fact)
        _draw_mini_glyph(draw, kind, x0 + 36, y0 + 40, pal)
        label, value = _split_lv(fact)
        if label and value:
            draw.text((x0 + 70, y0 + 28), label[:22], fill=pal["muted"], font=label_f)
            draw.text((x0 + 70, y0 + 58), value[:28], fill=pal["text"], font=value_f)
        else:
            for j, wl in enumerate(_wrap_lines(draw, fact[:70], label_f, col_w - 90, max_lines=2)):
                draw.text((x0 + 70, y0 + 40 + j * 28), wl, fill=pal["text"], font=label_f)

    _round_rect(draw, (margin, height - 72, width - margin, height - margin), 14, pal["card"])
    foot = pillow_font(16, bold=False)
    foot_txt = "Thông tin địa điểm · Unicode" if has_place else "Bản tin trực quan · Unicode"
    draw.text((margin + 24, height - 56), foot_txt, fill=pal["muted"], font=foot)

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
        return
    if k == "uv":
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=pal["sun"])
        return
    if k == "rain":
        draw.ellipse((cx - 12, cy - 8, cx + 8, cy + 8), fill=pal["cloud"])
        draw.line((cx - 2, cy + 10, cx - 6, cy + 22), fill=pal["accent"], width=3)
        return
    if k == "cloud":
        draw.ellipse((cx - 12, cy - 4, cx + 6, cy + 12), fill=pal["cloud"])
        draw.ellipse((cx - 2, cy - 12, cx + 14, cy + 6), fill=pal["cloud"])
        return
    if k == "temp":
        draw.rounded_rectangle((cx - 4, cy - 14, cx + 4, cy + 4), radius=3, fill=pal["accent"])
        draw.ellipse((cx - 8, cy + 2, cx + 8, cy + 18), fill=pal["sun"])
        return
    draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=pal["sun"])


def render_weather_banner_bytes(prompt: str, *, style: str = "daylight") -> bytes:
    """Wide banner used inside styled PDFs."""
    return render_info_card_bytes(prompt, width=1200, height=520, style=style or "daylight")


def render_info_card_variants(prompt: str) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for name in _STYLES:
        out.append((name, render_info_card_bytes(prompt, style=name)))
    return out
