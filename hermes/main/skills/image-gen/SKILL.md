---
name: image-gen
description: "Generate still images via dispatcher POST /v1/image using router combo image-gen when Media worker is active, else hermes. RESULT-ONLY (see media-out)."
---

# Image generation

Follow skill **`media-out`** (result only — no step chatter, no approve, no chat_id / names / DM metadata).

The built-in Hermes `image_generation` tool is often **unavailable**. Do **not** stop. Do **not** invent matplotlib, PIL scripts, HTML screenshots, or new skills.

**This stack path (required):** `POST http://dispatcher:8090/v1/image`

Diffusion uses router combo (never a single hardcoded model id):

1. Media worker **active** → combo **`image-gen`** (Omni `/images/generations`, then 9Router if enabled)
2. Media worker **inactive** → combo **`hermes`**

**Default canvas (HD):** pass `"size":"1024x1024"` on the request body unless the user asks for another size. Do not rely on env or dispatcher hardcodes for size.

Local Pillow modes (no router): `"mode":"info-card"` and `"mode":"text-poster"`.

If `/v1/image` returns 502/503: one **media-out** failure line only. When the ask was primarily a **PDF/office file**, finish via **`file-gen`**.

## Modes

| Need | Call |
|------|------|
| Scenic / illustration | default `/v1/image` with English scene prompt; optional `overlay[]` |
| Labeled metrics picture | `"mode":"info-card"` + TITLE/SUBTITLE/ICON markers |
| Exact text poster | `"mode":"text-poster"` |

```bash
mkdir -p /opt/data/media/out && curl -sS -X POST http://dispatcher:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"<scene>","filename":"<safe-slug>.png","refine":false,"size":"1024x1024"}'
```

## Output

Only `/opt/data/media/out/<safe-slug>.png` (or `.jpg`).

## Related

- `multi-purpose`, `vision-ocr`, `video-gen`, `file-gen`
