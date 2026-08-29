# -*- coding: utf-8 -*-
"""Full-page weather sheet (Pillow) for attractive office-file PDFs.

Layout inspired by modern weather-app cards: one hero temperature, one large
condition icon, and a clean metric grid — no badge-strip clutter.
"""
from __future__ import annotations

import math
from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw

from fonts import pillow_font


def _parse_body(prompt: str) -> dict[str, Any]:
    title = ""
    subtitle = ""
    icon = "sun"
    overview = ""
    background = ""
    facts: list[str] = []
    for raw in (prompt or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("TITLE:", "Title:", "title:")):
            title = line.split(":", 1)[1].strip()
            continue
        if line.startswith(("SUBTITLE:", "Subtitle:", "subtitle:")):
            subtitle = line.split(":", 1)[1].strip()
            continue
        if line.startswith(("ICON:", "Icon:", "icon:")):
            icon = line.split(":", 1)[1].strip().split()[0].lower() or "sun"
            if "|" in icon:
                icon = icon.split("|", 1)[0].strip() or "sun"
            continue
        if line.startswith(("OVERVIEW:", "Overview:", "overview:")):
            overview = line.split(":", 1)[1].strip()
            continue
        if line.startswith(("BACKGROUND:", "Background:", "background:")):
            background = line.split(":", 1)[1].strip()
            continue
        if line.startswith(("- ", "• ", "* ")):
            facts.append(line[2:].strip())
        else:
            facts.append(line)
    if not title and facts:
        title = facts.pop(0)
    return {
        "title": title or "Cập nhật",
        "subtitle": subtitle or "Cập nhật trực tiếp",
        "icon": icon,
        "overview": overview,
        "background": background,
        "facts": facts,
    }


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
                if not t:
                    continue
                if "°" in t or "º" in t:
                    after = t.split("°", 1)[-1].split("º", 1)[-1].upper()
                    if after and after[0].isalpha() and not after.startswith(("C", "F")):
                        continue
                if t.endswith(("°C", "ºC")) or "℃" in t:
                    return t
                if t.replace(".", "", 1).isdigit():
                    return f"{t}°C"
    for fact in facts:
        for token in fact.replace(",", " ").split():
            t = token.strip()
            if t.endswith(("°C", "ºC")) or "℃" in t:
                return t
    return ""


def _metric_kind(label: str, value: str) -> str:
    low = f"{label} {value}".lower()
    if any(x in low for x in ("nhiệt", "temp", "feels", "cảm giác")):
        return "temp"
    if any(x in low for x in ("ẩm", "humid")):
        return "humidity"
    if any(x in low for x in ("gió", "wind")):
        return "wind"
    if any(x in low for x in ("uv",)):
        return "uv"
    if any(x in low for x in ("mưa", "rain", "precip")):
        return "rain"
    if any(x in low for x in ("mây", "cloud", "tình trạng", "condition")):
        return "condition"
    return "default"


def _palette(icon: str) -> dict[str, tuple[int, int, int]]:
    kind = (icon or "sun").lower()
    if kind in {"rain", "storm", "mưa", "mua"}:
        return {
            "sky_top": (70, 110, 170),
            "sky_bot": (160, 190, 230),
            "card": (255, 255, 255),
            "card_soft": (242, 247, 255),
            "text": (28, 40, 58),
            "muted": (100, 120, 145),
            "accent": (55, 110, 190),
            "sun": (255, 205, 70),
            "cloud": (220, 230, 240),
        }
    if kind in {"cloud", "cloudy", "mây", "overcast"}:
        return {
            "sky_top": (110, 140, 175),
            "sky_bot": (200, 215, 230),
            "card": (255, 255, 255),
            "card_soft": (245, 248, 252),
            "text": (30, 42, 58),
            "muted": (105, 122, 145),
            "accent": (80, 120, 170),
            "sun": (255, 200, 80),
            "cloud": (210, 220, 230),
        }
    # sun / clear default
    return {
        "sky_top": (55, 145, 220),
        "sky_bot": (170, 215, 250),
        "card": (255, 255, 255),
        "card_soft": (245, 250, 255),
        "text": (25, 40, 60),
        "muted": (95, 115, 140),
        "accent": (30, 120, 210),
        "sun": (255, 195, 50),
        "cloud": (235, 242, 250),
    }


def _grad(im: Image.Image, top: tuple[int, int, int], bot: tuple[int, int, int]) -> None:
    w, h = im.size
    px = im.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)


def _draw_icon(draw: ImageDraw.ImageDraw, icon: str, cx: int, cy: int, pal: dict, scale: float = 1.0) -> None:
    kind = (icon or "sun").lower()
    r = int(48 * scale)
    if kind in {"rain", "storm", "mưa", "mua"}:
        draw.ellipse((cx - 40, cy - 18, cx + 8, cy + 22), fill=pal["cloud"])
        draw.ellipse((cx - 12, cy - 30, cx + 42, cy + 18), fill=pal["cloud"])
        draw.ellipse((cx - 22, cy - 8, cx + 22, cy + 28), fill=pal["cloud"])
        for i in range(5):
            x = cx - 22 + i * 12
            draw.line((x, cy + 30, x - 6, cy + 52), fill=pal["accent"], width=4)
        if kind == "storm":
            draw.polygon(
                [(cx + 8, cy + 8), (cx - 4, cy + 30), (cx + 10, cy + 30), (cx - 2, cy + 54)],
                fill=pal["sun"],
            )
        return
    if kind in {"cloud", "cloudy", "mây", "overcast"}:
        draw.ellipse((cx - 42, cy - 8, cx + 6, cy + 32), fill=pal["cloud"])
        draw.ellipse((cx - 10, cy - 28, cx + 44, cy + 22), fill=pal["cloud"])
        draw.ellipse((cx - 24, cy, cx + 24, cy + 36), fill=pal["cloud"])
        draw.ellipse((cx + 16, cy - 34, cx + 48, cy - 2), fill=pal["sun"])
        return
    draw.ellipse((cx - int(r * 0.55), cy - int(r * 0.55), cx + int(r * 0.55), cy + int(r * 0.55)), fill=pal["sun"])
    for i in range(12):
        ang = i * math.pi / 6
        draw.line(
            (
                cx + int(math.cos(ang) * r * 0.75),
                cy + int(math.sin(ang) * r * 0.75),
                cx + int(math.cos(ang) * r * 1.25),
                cy + int(math.sin(ang) * r * 1.25),
            ),
            fill=pal["sun"],
            width=5,
        )


def _draw_metric_glyph(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, pal: dict) -> None:
    k = (kind or "default").lower()
    if k == "temp":
        draw.rounded_rectangle((cx - 5, cy - 16, cx + 5, cy + 6), radius=4, fill=pal["accent"])
        draw.ellipse((cx - 10, cy + 2, cx + 10, cy + 20), fill=pal["sun"])
        return
    if k == "humidity":
        draw.polygon([(cx, cy - 16), (cx - 12, cy + 2), (cx + 12, cy + 2)], fill=pal["accent"])
        draw.ellipse((cx - 12, cy - 2, cx + 12, cy + 18), fill=pal["accent"])
        return
    if k == "wind":
        draw.arc((cx - 16, cy - 12, cx + 16, cy + 8), 200, 340, fill=pal["accent"], width=3)
        draw.arc((cx - 10, cy - 2, cx + 18, cy + 14), 200, 340, fill=pal["muted"], width=3)
        return
    if k == "uv":
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=pal["sun"])
        return
    if k == "rain":
        draw.ellipse((cx - 14, cy - 12, cx + 10, cy + 8), fill=pal["cloud"])
        draw.line((cx - 4, cy + 10, cx - 8, cy + 22), fill=pal["accent"], width=3)
        draw.line((cx + 4, cy + 10, cx, cy + 22), fill=pal["accent"], width=3)
        return
    if k == "condition":
        draw.ellipse((cx - 14, cy - 6, cx + 6, cy + 12), fill=pal["cloud"])
        draw.ellipse((cx - 4, cy - 14, cx + 16, cy + 6), fill=pal["cloud"])
        return
    draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=pal["accent"])


def _wrap_draw(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    *,
    font: Any,
    fill: tuple[int, int, int],
    max_width: int,
    max_lines: int = 3,
    line_gap: int = 6,
) -> int:
    """Draw wrapped text; return y after last line."""
    words = (text or "").split()
    if not words:
        return xy[1]
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
                break
    if len(lines) < max_lines:
        lines.append(cur)
    x, y = xy
    for i, line in enumerate(lines[:max_lines]):
        draw.text((x, y), line, fill=fill, font=font)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def render_weather_sheet_bytes(prompt: str, *, width: int = 1240, height: int = 1754) -> bytes:
    """Portrait info sheet (~A4 @ 150dpi) — place overview + metrics when present."""
    meta = _parse_body(prompt)
    pal = _palette(meta["icon"])
    im = Image.new("RGB", (width, height), pal["sky_bot"])
    _grad(im, pal["sky_top"], pal["sky_bot"])
    draw = ImageDraw.Draw(im)

    margin = 48
    # Soft white sheet card
    sheet = (margin, margin, width - margin, height - margin)
    draw.rounded_rectangle(sheet, radius=36, fill=pal["card"])

    has_place = bool(meta.get("overview") or meta.get("background"))
    # Inner sky band — taller when place overview/background present
    band_frac = 0.46 if has_place else 0.38
    band_bottom = margin + int((height - 2 * margin) * band_frac)
    draw.rounded_rectangle(
        (margin + 20, margin + 20, width - margin - 20, band_bottom),
        radius=28,
        fill=pal["sky_top"],
    )
    draw.rounded_rectangle(
        (margin + 20, band_bottom - 100, width - margin - 20, band_bottom),
        radius=24,
        fill=pal["sky_bot"],
    )

    title_f = pillow_font(38, bold=True)
    sub_f = pillow_font(22, bold=False)
    hero_f = pillow_font(112, bold=True)
    cond_f = pillow_font(30, bold=False)
    body_f = pillow_font(22, bold=False)
    label_sm = pillow_font(18, bold=True)

    title = meta["title"][:42]
    draw.text((margin + 48, margin + 48), title, fill=(255, 255, 255), font=title_f)
    draw.text((margin + 48, margin + 100), meta["subtitle"][:48], fill=(230, 240, 255), font=sub_f)

    _draw_icon(draw, meta["icon"], width - margin - 160, margin + 230, pal, scale=2.1)

    y_cursor = margin + 140
    if meta.get("overview"):
        draw.text((margin + 48, y_cursor), "Tổng quan", fill=(200, 220, 245), font=label_sm)
        y_cursor = _wrap_draw(
            draw,
            meta["overview"][:180],
            (margin + 48, y_cursor + 26),
            font=body_f,
            fill=(245, 250, 255),
            max_width=width - 2 * margin - 280,
            max_lines=3,
        )
    if meta.get("background"):
        y_cursor += 8
        draw.text((margin + 48, y_cursor), "Bối cảnh", fill=(200, 220, 245), font=label_sm)
        y_cursor = _wrap_draw(
            draw,
            meta["background"][:180],
            (margin + 48, y_cursor + 26),
            font=body_f,
            fill=(235, 245, 255),
            max_width=width - 2 * margin - 280,
            max_lines=3,
        )

    hero = _hero_temp(meta["facts"])
    hero_y = max(y_cursor + 12, margin + 200) if has_place else margin + 200
    if hero and not has_place:
        draw.text((margin + 48, hero_y), hero, fill=(255, 255, 255), font=hero_f)
    elif hero and has_place:
        # Compact hero when overview takes the band
        compact = pillow_font(56, bold=True)
        draw.text((margin + 48, min(hero_y, band_bottom - 90)), hero, fill=(255, 255, 255), font=compact)

    condition = ""
    metrics: list[tuple[str, str, str]] = []
    for fact in meta["facts"]:
        label, value = _split_lv(fact)
        kind = _metric_kind(label, value)
        if kind == "temp" and hero:
            continue
        if kind == "condition" and not condition:
            condition = value or label
        metrics.append((label or "Chi tiết", value or fact, kind))
    if condition and not has_place:
        draw.text((margin + 48, margin + 340), condition[:40], fill=(235, 245, 255), font=cond_f)
    elif meta["icon"] and not has_place:
        pretty = {"sun": "Trời nắng", "cloud": "Nhiều mây", "rain": "Có mưa", "storm": "Giông bão"}.get(
            meta["icon"], ""
        )
        if pretty:
            draw.text((margin + 48, margin + 340), pretty, fill=(235, 245, 255), font=cond_f)

    # Metric grid fills remaining sheet (2 columns, larger tiles)
    metrics = metrics[:6]
    grid_top = band_bottom + 36
    cols = 2
    gap = 22
    usable_h = height - margin - 70 - grid_top
    rows = max(1, (len(metrics) + cols - 1) // cols) if metrics else 1
    card_w = (width - 2 * margin - 40 - gap) // cols
    card_h = max(150, min(200, (usable_h - gap * (rows - 1)) // max(rows, 1)))
    label_f = pillow_font(20, bold=False)
    value_f = pillow_font(34, bold=True)
    for i, (label, value, kind) in enumerate(metrics):
        col = i % cols
        row = i // cols
        x0 = margin + 20 + col * (card_w + gap)
        y0 = grid_top + row * (card_h + gap)
        fill = pal["card_soft"] if (row + col) % 2 == 0 else (248, 250, 252)
        draw.rounded_rectangle((x0, y0, x0 + card_w, y0 + card_h), radius=22, fill=fill)
        draw.ellipse((x0 + 22, y0 + card_h // 2 - 32, x0 + 86, y0 + card_h // 2 + 32), fill=(255, 255, 255))
        _draw_metric_glyph(draw, kind, x0 + 54, y0 + card_h // 2, pal)
        draw.text((x0 + 106, y0 + card_h // 2 - 28), label[:22], fill=pal["muted"], font=label_f)
        draw.text((x0 + 106, y0 + card_h // 2 + 4), value[:28], fill=pal["text"], font=value_f)

    foot = pillow_font(18, bold=False)
    foot_label = "Thông tin địa điểm" if has_place else "Bản tin cập nhật"
    draw.text((margin + 36, height - margin - 40), foot_label, fill=pal["muted"], font=foot)

    buf = BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def layout_score_from_text(extracted: str) -> list[str]:
    """Return list of layout problems found in extracted PDF text (empty = ok)."""
    problems: list[str] = []
    text = extracted or ""
    # Old cluttered badge strip
    if "Nắng Mây Mưa Giông" in text or "Nhiệt Ẩm Gió UV" in text:
        problems.append("badge_strip_clutter")
    if "biểu tượng + hình minh họa" in text:
        problems.append("debug_footer")
    # empty_text is interpreted with file-size context in verify_styled_pdf_layout
    if not text.strip():
        problems.append("empty_text")
    return problems
