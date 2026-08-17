---
name: image-gen
description: "Generate images via dispatcher. Use text-poster path for exact quoted text / N lines (fill in, lines, poster, black and white). Use diffusion only for art/scenes without readable text. RESULT-ONLY (see media-out)."
---

# Image generation

Follow skill **`media-out`** (result only — no step chatter, no approve, no chat_id / names / DM metadata).

## Output path

Only `/opt/data/media/out/<safe-slug>.png` (or `.jpg`). Never `/opt/data/<file>.png` or `/tmp`.

## Exact text posters (must — read first)

When the user wants **readable exact text** on an image:

- Quoted phrase plus **N lines / fill in / fill with / poster / text**
- **Black and white** typography
- Example: `create a black and white image, fill in 10 lines "SAMPLE TEXT"`

**Do not** use diffusion, ComfyUI, LLM prompt refine, or artistic/canvas-design skills for these — they rewrite text into illegible calligraphy.

Post the **verbatim user sentence** (keep quotes). Dispatcher auto-detects and renders with Pillow (`backend: text-poster`): N identical centered lines of the exact phrase.

```bash
mkdir -p /opt/data/media/out && curl -sS -X POST http://dispatcher:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"<verbatim user request>","filename":"<safe-slug>.png","refine":false}'
```

Optional explicit mode: `"mode":"text"` or `"provider":"text"`.

Success: `"ok":true`, `"backend":"text-poster"`, `"n"`, `"phrase"`. Confirm the phrase matches the user quote before replying.

## Artistic / scene images (diffusion)

Only when the user wants illustration, photo, or art **without** exact readable text blocks:

```bash
mkdir -p /opt/data/media/out && curl -sS -X POST http://dispatcher:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"<user request>","filename":"<safe-slug>.png","refine":false}'
```

Use `refine:true` only if the user explicitly wants an English art prompt rewrite. Do not install Pillow/pip/uv in Hermes — dispatcher owns rendering.

## Delivery

**Do not** set `send_zalo:true` and **do not** call `/v1/send-file` for the same image — Zalo autosend delivers **one** file from `/opt/data/media/out/`.

## User-facing reply (only this)

After `ok:true`: reply exactly `Đã xong.` (or `Done.`). Nothing else.

## Related

- `media-out` — result-only rules for all media
- `comfyui` — explicit Comfy workflow only; still `--output-dir /opt/data/media/out`
- `file-gen` — office docs only, not images
