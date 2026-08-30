---
name: image-gen
description: "Generate still images via dispatcher POST /v1/image using router combo image-gen (Omni /images/generations, then 9Router). RESULT-ONLY (see media-out)."
---

# Image generation

Follow skill **`media-out`** (result only — no step chatter, no approve, no chat_id / names / DM metadata).

The built-in Hermes `image_generation` tool is often **unavailable**. Do **not** stop. Do **not** invent matplotlib, PIL scripts, HTML screenshots, ComfyUI workflows, or new skills.

**This stack path (required):** `POST http://dispatcher:8090/v1/image`

Diffusion uses router combo **`image-gen`** (`IMAGE_GEN_COMBO`):

1. OmniRouter `POST /v1/images/generations` with `model=image-gen`
2. If `ENABLE_9ROUTER=1`, 9Router OpenAI-compatible `/images/generations` with the same combo name

Local Pillow modes (no router):

- `"mode":"info-card"` — labeled dashboards / readable metrics
- `"mode":"text-poster"` — exact readable text lines

**Never** call ComfyUI, fal, Flux cloud keys, Pollinations, or Gemini image APIs from Hermes.

If `/v1/image` returns 502/503: one **media-out** failure line only — do not ask for API keys or `.env`. When the ask was primarily a **PDF/office file**, finish via **`file-gen`**.

## Modes

| Need | Call |
|------|------|
| Scenic / illustration photo | default `/v1/image` with English scene prompt; optional `overlay[]` |
| Labeled metrics picture | `"mode":"info-card"` + TITLE/SUBTITLE/ICON/STYLE markers |
| Exact text poster | `"mode":"text-poster"` or verbatim poster sentence |

```bash
mkdir -p /opt/data/media/out && curl -sS -X POST http://dispatcher:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"<scene>","filename":"<safe-slug>.png","refine":false}'
```

## Output

Only `/opt/data/media/out/<safe-slug>.png` (or `.jpg`). Do **not** set `send_zalo:true` when autosend will deliver.

## Related

- `multi-purpose` — complex layout briefs via chat combo `hermes`, then image-gen / file-gen
- `vision-ocr` — read text from images
- `video-gen` — video/music/audio/transcripts refused
- `file-gen` — office docs
