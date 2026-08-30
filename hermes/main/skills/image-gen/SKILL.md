---
name: image-gen
description: "Generate still images via OmniRouter POST /v1/images/generations with combo image-gen (Media worker active or inactive). RESULT-ONLY (see media-out)."
---

# Image generation

Follow skill **`media-out`** (result only — no step chatter, no approve, no chat_id / names / DM metadata).

The built-in Hermes `image_generation` tool is often **unavailable**. Do **not** stop. Do **not** invent local drawing scripts, ComfyUI, or new skills.

## Diffusion (required for scenic / illustration)

Call **OmniRouter** directly — combo name **`image-gen`** always (Media worker active **or** inactive; never `model=hermes` for still diffusion, never ComfyUI, never dispatcher `/v1/image`):

`POST http://omni-router:20129/v1/images/generations`

- Auth: `Authorization: Bearer $OPENAI_API_KEY` (same as `OMNIROUTER_API_KEY`)
- Body: `model` = `image-gen` (or `$IMAGE_GEN_COMBO` when set), English `prompt`, `n=1`, HD `size` `"1024x1024"` unless the user asks otherwise
- Decode `data[0].b64_json` (or fetch `url`) and write under `/opt/data/media/out/<safe-slug>.png` (or `.jpg` / `.webp`)

```bash
mkdir -p /opt/data/media/out
curl -sS -X POST http://omni-router:20129/v1/images/generations \
  -H "authorization: Bearer ${OPENAI_API_KEY}" \
  -H 'content-type: application/json' \
  -d '{"model":"image-gen","prompt":"<english-scene>","n":1,"size":"1024x1024"}' \
  | python -c "import sys,json,base64; d=json.load(sys.stdin); x=(d[0] if isinstance(d,list) else (d.get('data') or [d])[0]); open('/opt/data/media/out/<safe-slug>.webp','wb').write(base64.b64decode(x['b64_json']))"
```

**Scenic prompts (any user language):** Prefer the classify `SCENE:` English line when present. Otherwise translate the user ask into one clear English diffusion sentence (viewpoint + place + photorealistic). Use official English place names — colloquial Saigon / Sài Gòn → Ho Chi Minh City (AI Horde falsely NSFW-blocks “Saigon”). Example family: `Ho Chi Minh City skyline, photorealistic`. Do not POST the raw non-English ask as the only prompt.

On Omni failure: one **media-out** failure line only. When the ask was primarily a **PDF/office file**, finish via **`file-gen`**.

## Local Pillow modes (not Omni diffusion)

Labeled cards / exact text posters only (not scenic diffusion):

| Need | Call |
|------|------|
| Labeled metrics picture | `POST http://dispatcher:8090/v1/info-card` |
| Exact text poster | `POST http://dispatcher:8090/v1/text-poster` |

Do **not** call deprecated `POST http://dispatcher:8090/v1/image` for scenic generation.

## Output

Only `/opt/data/media/out/<safe-slug>.*` (webp/png/jpg).

## Related

- `multi-purpose`, `vision-ocr`, `video-gen`, `file-gen`
