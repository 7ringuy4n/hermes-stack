---
name: infographic-design
description: "Default layout skill when generating an image that includes informational text (weather, fuel, prices, status). Professional infographic composition — not text dumped on a photo."
---

# Image text layout and infographic design

## When to use

**Default** whenever the user asks for an image that must show **readable informational text** (weather + fuel, city status, metrics, bilingual labels). Apply before calling dispatcher `POST /v1/image`.

Exact typography posters (verbatim quoted lines, black-and-white fill) stay on `image-gen` text-poster mode — not this skill.

## Purpose

Treat **visual composition and readability** as part of the task. Text must not simply be placed on top of the image.

Reference style:

- Main visual remains clearly visible
- Information grouped into clean sections
- Text occupies only a controlled portion of the image
- Translucent information panel when needed
- Font hierarchy: title, key values, labels, secondary info
- Result looks like a **professional infographic**, not a screenshot with overlays

## Layout rules

1. **Preserve the main image** — do not let text cover the whole scene; reserve space for information; prefer low-detail areas.
2. **Structured zones** — cards/panels; side, corner, or lower area; translucent backgrounds for contrast.
3. **Typography** — clean modern font with full Unicode/Vietnamese support; no decorative fonts that hurt readability.
4. **Hierarchy** — title largest; primary data (temp/price) emphasized; labels medium; source/date smaller.
5. **Fit to canvas** — wrap, pad, and resize so nothing clips or overflows.
6. **Avoid excess coverage** — concise wording; do not let text blocks dominate.
7. **Balance** — align, pad, avoid busy backgrounds without a panel.
8. **Readability** — sufficient contrast; subtle panel/shadow when needed.

## Recommended structure

```text
┌──────────────────────────────────────────────┐
│ TITLE / LOCATION                            │
│ Update date                                 │
│                                              │
│ ┌──────────── INFORMATION PANEL ──────────┐ │
│ │ Weather icon    Primary value            │ │
│ │                 Condition                │ │
│ │ ─────────────────────────────────────── │ │
│ │ Humidity / Wind / Visibility             │ │
│ └─────────────────────────────────────────┘ │
│                                              │
│ ┌──────────── SECONDARY PANEL ────────────┐ │
│ │ Fuel / Prices / Key Metrics              │ │
│ └─────────────────────────────────────────┘ │
│                                              │
│ Source / secondary                          │
│                 MAIN IMAGE / LANDMARK       │
└──────────────────────────────────────────────┘
```

Information area ≈ one side or corner; majority of canvas stays the main visual.

## Dispatcher usage

1. Gather short fact lines (search if needed).
2. Build a **scene prompt** that describes the landmark/weather view **and** asks for the infographic layout above.
3. Pass facts as `overlay: ["…", "…"]` on `POST /v1/image` (Vietnamese when the user asked for Vietnamese).
4. Follow `media-out` — file only, no process chatter.

## Final checks

- [ ] All text visible, no clipping
- [ ] Vietnamese/UTF-8 correct
- [ ] Clear hierarchy; main image still dominant
- [ ] Contrast sufficient; balanced composition

## Core instruction

When embedding text into an image, design the layout around the image content first. Use a clean Unicode-capable font and clear hierarchy. Adjust size, wrap, spacing, and panels so text fits. Keep text grouped in a limited area; preserve the main scene as the dominant visual.
