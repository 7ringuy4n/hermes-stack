---
name: image-gen
description: "Generate images via dispatcher POST /v1/image (default). Overlay facts with overlay[]. Never invent matplotlib/PIL. RESULT-ONLY (see media-out)."
---

# Image generation

Follow skill **`media-out`** (result only — no step chatter, no approve, no chat_id / names / DM metadata).

The built-in Hermes `image_generation` tool is often **unavailable** (cloud keys / BFL). Do **not** stop. Do **not** invent matplotlib, PIL scripts, HTML screenshots, or new skills.

**This stack path (required):** `POST http://dispatcher:8090/v1/image` with `IMAGE_BACKENDS=comfy-cpu,comfy-gpu,omni`. ComfyUI is tried first; on failure dispatcher falls back to OmniRouter (`/images/generations`). Skill `comfyui` is only for an explicit Comfy workflow the user named — default image gen is always dispatcher.

If `/v1/image` returns 502/503 or backends are unavailable: **do not** ask the user for API keys, `.env`, ComfyUI, or Omni auth. **Do not** send session-restore or numbered recovery menus. When the user’s ask was primarily a **PDF/office file** with icons/layout, finish via **`file-gen`** / office-file (styled PDF) instead of retrying image gen forever.

For **weather / fuel / info dashboards as a picture** (readable Vietnamese labels), prefer `"mode":"info-card"` on `POST /v1/image` with TITLE/ICON/STYLE/fact lines — Pillow + Noto fonts. **Do not** ask diffusion to paint Vietnamese text (it becomes tofu/boxes).

Generate through this skill and dispatcher instead.

**Never** `web_search`, `web_extract`, or browse GitHub/release/news pages to “find image URLs”. That is not generation. Users must receive a **new file** from dispatcher, not a scrape of someone else’s page. If weather/fuel context is needed, one short search for conditions is enough, then `POST /v1/image` with a **scene prompt** plus `overlay` fact lines (Vietnamese when the user asked for Vietnamese). If dispatcher fails: one failure line from **media-out**, then stop.

## Output path

Only `/opt/data/media/out/<safe-slug>.png` (or `.jpg`). Never `/opt/data/<file>.png` or `/tmp`.

## Exact text posters (must — read first)

When the user wants **readable exact text** on an image:

- Quoted phrase plus **N lines / fill in / fill with / poster / text**
- Unquoted: `5 dòng hello`, `điền vào 5 dòng hello`, `vẽ … 5 dòng hello`
- **Black and white** typography
- Example: `create a black and white image, fill in 10 lines "SAMPLE TEXT"`

**Do not** use diffusion, ComfyUI, LLM prompt refine, or artistic/canvas-design skills for these — they rewrite text into illegible calligraphy / unrelated photos.

Post the **verbatim user sentence** (keep quotes). Dispatcher auto-detects and renders with Pillow (`backend: text-poster`): N identical centered lines of the exact phrase. Optional `"mode":"text-poster"`.

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
  -d '{"prompt":"<scene>","filename":"<safe-slug>.png","refine":false,"overlay":["<short fact 1>","<short fact 2>"]}'
```

## Infographic (default when the image must show informational text)

When the user wants **weather / fuel / prices / metrics on the picture** (readable facts + scene), follow skill **`image-gen/infographic-design`** first: layout, hierarchy, panels, Unicode. Then `POST /v1/image` with a scene prompt plus `overlay` fact lines. Do not dump text randomly on the photo.

Use `refine:true` only if the user explicitly wants an English art prompt rewrite. Do not install Pillow/pip/uv in Hermes — dispatcher owns rendering. Put live weather and fuel **on the image** via `overlay` (already-fetched strings), not as a separate chat message unless the user asked for text as well.

## Delivery

**Do not** set `send_zalo:true` and **do not** call `/v1/send-file` for the same image — Zalo autosend delivers **one** file from `/opt/data/media/out/`.

## User-facing reply (only this)

After `ok:true`: send the file only (autosend). No success ack line. If the user also asked for facts, put those facts in the same job’s reply without process chatter.

## Related

- `media-out` — result-only rules for all media
- `video-gen` — video clips refused (policy); still images via `image-gen`
- `comfyui` — explicit Comfy workflow only; still `--output-dir /opt/data/media/out`
- `file-gen` — office docs only, not images
