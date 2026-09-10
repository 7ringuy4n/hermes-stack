---
name: infographic-design
description: "Default layout skill when generating an image that includes informational text (prices, metrics, status, labeled facts). Professional infographic composition via diffusion — not Pillow overlays."
---

# Image text layout and infographic design

## When to use

**Default** whenever the user asks for an image that must show **readable informational text** (metrics, prices, city status, bilingual labels). Apply before calling Omni combo **image-gen**.

Exact typography posters (verbatim quoted lines, black-and-white fill) stay on dispatcher `text-poster` mode — not this skill.

## Purpose

Treat **visual composition and readability** as part of the diffusion SCENE prompt. Text must not simply be dumped on a photo by host-side layout code.

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

## Omni image-gen usage

1. Gather short fact lines (search if needed).
2. Build one English **SCENE** prompt that describes the landmark/context view **and** asks for the infographic layout above.
3. Append fact bullets in the SCENE (or as `-` lines from classify) matching the user’s language for on-image labels.
4. `POST http://omni-router:20129/v1/images/generations` with `model=image-gen`.
5. Follow `media-out` — file only, no process chatter.

## Final checks

- [ ] All text visible, no clipping
- [ ] Vietnamese/UTF-8 correct
- [ ] Clear hierarchy; main image still dominant
- [ ] Contrast sufficient; balanced composition

## Core instruction

When embedding text into an image, design the layout around the image content first in the SCENE prompt. Keep text grouped in a limited area; preserve the main scene as the dominant visual. Use safe-for-work daytime outdoor framing and official English place names when a city is the subject.
