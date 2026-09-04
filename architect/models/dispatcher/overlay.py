# -*- coding: utf-8 -*-
"""Render a validated, model-authored information layer onto an existing image."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageStat

from fonts import pillow_font

MAX_OVERLAY_LINES = 6
MIN_FONT = 13
MAX_BOX_RATIO = 0.46

_PLACEMENTS = {"auto", "top-left", "top-right", "bottom-left", "bottom-right", "bottom-bar"}
_THEMES = {"auto", "light", "dark"}
_ALIGNMENTS = {"left", "center", "right"}
_WEIGHTS = {"regular", "medium", "semibold", "bold"}
_FAMILIES = {"auto", "inter", "noto-sans", "serif", "mono"}
_ACCENTS = {"auto", "cool", "warm", "neutral", "vibrant"}


def _choice(raw: Any, allowed: set[str], fallback: str) -> str:
    value = str(raw or "").strip().lower()
    return value if value in allowed else fallback


def clean_overlay_lines(lines: Sequence[str] | None, *, limit: int = MAX_OVERLAY_LINES) -> list[str]:
    """Keep short non-empty lines and reject incomplete protocol artifacts."""
    out: list[str] = []
    for raw in lines or []:
        value = " ".join(str(raw or "").split())
        if not value:
            continue
        lowered = value.lower()
        if "<" in value or ">" in value or "value after" in lowered:
            continue
        if value.upper().startswith(("SCENE:", "RENDER:")):
            continue
        out.append(value[:120])
        if len(out) >= limit:
            break
    return out


def wrap_text_to_width(
    text: str, font: ImageFont.ImageFont, max_w: int, draw: ImageDraw.ImageDraw
) -> list[str]:
    """Split on spaces so each line's pixel width is within max_w."""
    raw = " ".join(str(text or "").split())
    if not raw or max_w <= 0:
        return [raw] if raw else []
    words = raw.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        bounds = draw.textbbox((0, 0), trial, font=font)
        if bounds[2] - bounds[0] <= max_w:
            current = trial
            continue
        if current:
            lines.append(current)
        word_bounds = draw.textbbox((0, 0), word, font=font)
        if word_bounds[2] - word_bounds[0] <= max_w:
            current = word
            continue
        chunk = ""
        for character in word:
            candidate = chunk + character
            candidate_bounds = draw.textbbox((0, 0), candidate, font=font)
            if chunk and candidate_bounds[2] - candidate_bounds[0] > max_w:
                lines.append(chunk)
                chunk = character
            else:
                chunk = candidate
        current = chunk
    if current:
        lines.append(current)
    return lines or [raw]


def _role_weight(role: str, design: dict[str, Any]) -> str:
    if role == "title":
        key = "title_weight"
    elif role in {"primary", "important"}:
        key = "important_weight"
    else:
        key = "body_weight"
    fallback = "semibold" if role == "title" else "regular"
    return _choice(design.get(key), _WEIGHTS, fallback)


def _layout_box(
    facts: Sequence[str],
    roles: Sequence[str],
    *,
    width: int,
    height: int,
    draw: ImageDraw.ImageDraw,
    max_box_w: int,
    design: dict[str, Any],
) -> tuple[int, int, int, list[tuple[str, int, ImageFont.ImageFont, str]]]:
    density = _choice(design.get("density"), {"compact", "comfortable"}, "comfortable")
    pad = max(10, width // (54 if density == "compact" else 46))
    inner_max_w = max(32, max_box_w - pad * 2)
    max_box_h = max(48, int(height * MAX_BOX_RATIO))
    base_size = max(MIN_FONT, min(30, width // 27))
    family = _choice(design.get("font_family"), _FAMILIES, "auto")
    fitted: list[tuple[str, int, ImageFont.ImageFont, str]] = []
    box_w = pad * 2
    box_h = pad * 2
    for _ in range(16):
        gap = max(3, base_size // (7 if density == "compact" else 5))
        rows: list[tuple[str, int, ImageFont.ImageFont, str]] = []
        total_h = pad * 2
        max_line_w = 0
        for index, fact in enumerate(facts):
            role = roles[index] if index < len(roles) else "normal"
            delta = 2 if role == "title" else (-2 if role == "meta" else 0)
            font = pillow_font(
                max(MIN_FONT, base_size + delta),
                weight=_role_weight(role, design),
                family=family,
            )
            for line in wrap_text_to_width(fact, font, inner_max_w, draw):
                bounds = draw.textbbox((0, 0), line, font=font)
                line_h = max(1, bounds[3] - bounds[1])
                line_w = bounds[2] - bounds[0]
                rows.append((line, line_h, font, role))
                max_line_w = max(max_line_w, line_w)
                total_h += line_h
        if rows:
            total_h += gap * (len(rows) - 1)
        box_w = min(max_box_w, max(pad * 2, max_line_w + pad * 2))
        if rows and (total_h <= max_box_h or base_size <= MIN_FONT):
            fitted = rows
            box_h = min(total_h, max_box_h, height)
            break
        base_size = max(MIN_FONT, base_size - 1)
    return pad, box_w, box_h, fitted


def _box_xy(
    placement: str, *, width: int, height: int, box_w: int, box_h: int, margin: int
) -> tuple[int, int]:
    if placement == "bottom-bar":
        return 0, height - box_h
    right = placement.endswith("right")
    top = placement.startswith("top")
    x = width - box_w - margin if right else margin
    y = margin if top else height - box_h - margin
    return x, y


def _region_stats(im: Image.Image, box: tuple[int, int, int, int]) -> tuple[float, float]:
    sample = im.convert("L").crop(box).resize((32, 32))
    stat = ImageStat.Stat(sample)
    return float(stat.mean[0]), float(stat.var[0])


def _auto_placement(im: Image.Image, *, box_w: int, box_h: int, margin: int) -> str:
    choices = ("top-left", "top-right", "bottom-left", "bottom-right")
    scored: list[tuple[float, str]] = []
    for placement in choices:
        x, y = _box_xy(
            placement,
            width=im.width,
            height=im.height,
            box_w=box_w,
            box_h=box_h,
            margin=margin,
        )
        mean, variance = _region_stats(im, (x, y, x + box_w, y + box_h))
        scored.append((variance + abs(mean - 128.0) * 0.15, placement))
    return min(scored)[1]


def _colors(
    theme: str, accent: str, mean: float
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    selected_theme = theme if theme != "auto" else ("light" if mean > 160 else "dark")
    if selected_theme == "light":
        panel = (248, 250, 252, 222)
        text = (18, 26, 38, 255)
    else:
        panel = (8, 16, 28, 210)
        text = (248, 252, 255, 255)
    accents = {
        "cool": (91, 200, 255, 255),
        "warm": (255, 183, 77, 255),
        "neutral": (190, 200, 212, 255),
        "vibrant": (114, 239, 164, 255),
    }
    chosen = accents.get(accent)
    if chosen is None:
        chosen = (45, 116, 150, 255) if selected_theme == "light" else (120, 210, 255, 255)
    return panel, text, chosen


def apply_overlay(
    path: Path,
    lines: Sequence[str],
    *,
    corner: str = "auto",
    design: dict[str, Any] | None = None,
) -> None:
    """Paint a responsive information layer using validated design controls."""
    facts = clean_overlay_lines(lines)
    if not facts:
        return
    style = dict(design) if isinstance(design, dict) else {}
    raw_roles = style.get("line_roles")
    roles = [str(item).strip().lower() for item in raw_roles] if isinstance(raw_roles, list) else []
    placement = _choice(style.get("placement") or corner, _PLACEMENTS, "auto")
    image = Image.open(path).convert("RGB")
    width, height = image.size
    measure = ImageDraw.Draw(image)
    max_box_w = width if placement == "bottom-bar" else max(120, int(width * 0.46))
    pad, box_w, box_h, rows = _layout_box(
        facts,
        roles,
        width=width,
        height=height,
        draw=measure,
        max_box_w=max_box_w,
        design=style,
    )
    if not rows:
        return
    margin = max(12, width // 40)
    if placement == "auto":
        placement = _auto_placement(image, box_w=box_w, box_h=box_h, margin=margin)
    if placement == "bottom-bar":
        box_w = width
    x0, y0 = _box_xy(
        placement,
        width=width,
        height=height,
        box_w=box_w,
        box_h=box_h,
        margin=margin,
    )
    mean, _variance = _region_stats(image, (x0, y0, x0 + box_w, y0 + box_h))
    panel, text_color, accent_color = _colors(
        _choice(style.get("theme"), _THEMES, "auto"),
        _choice(style.get("accent"), _ACCENTS, "auto"),
        mean,
    )
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.rounded_rectangle(
        (x0, y0, x0 + box_w, y0 + box_h),
        radius=max(8, min(20, box_w // 12)),
        fill=panel,
    )
    composed = Image.alpha_composite(image.convert("RGBA"), layer)
    output_draw = ImageDraw.Draw(composed)
    density = _choice(style.get("density"), {"compact", "comfortable"}, "comfortable")
    gap = max(3, width // (210 if density == "compact" else 170))
    alignment = _choice(style.get("alignment"), _ALIGNMENTS, "left")
    y = y0 + pad
    for text, line_h, font, role in rows:
        if y + line_h > y0 + box_h - 2:
            break
        bounds = output_draw.textbbox((0, 0), text, font=font)
        line_w = bounds[2] - bounds[0]
        if alignment == "center":
            x = x0 + max(pad, (box_w - line_w) // 2)
        elif alignment == "right":
            x = x0 + box_w - pad - line_w
        else:
            x = x0 + pad
        fill = accent_color if role in {"title", "primary"} else text_color
        output_draw.text((x, y), text, fill=fill, font=font)
        y += line_h + gap
    output = composed.convert("RGB")
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        output.save(path, quality=92)
    else:
        output.save(path)
    try:
        path.chmod(0o664)
    except OSError:
        pass
