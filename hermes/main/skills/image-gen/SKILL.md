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
- Body: `model` = `image-gen` (or `$IMAGE_GEN_COMBO` when set), English `prompt`, `n=1`, HD `size` `"1920x1080"` (16:9 Full HD) unless the user asks otherwise
- Decode `data[0].b64_json` (or fetch `url`) and write under `/opt/data/media/out/<safe-slug>.png` (or `.jpg` / `.webp`)

```bash
mkdir -p /opt/data/media/out
curl -sS -X POST http://omni-router:20129/v1/images/generations \
  -H "authorization: Bearer ${OPENAI_API_KEY}" \
  -H 'content-type: application/json' \
  -d '{"model":"image-gen","prompt":"<english-scene>","n":1,"size":"1920x1080"}' \
  | python -c "import sys,json,base64; d=json.load(sys.stdin); items=(d if isinstance(d,list) else (d.get('data') or d.get('images') or [d])); x=items[0]; open('/opt/data/media/out/<safe-slug>.webp','wb').write(base64.b64decode(x['b64_json']) if x.get('b64_json') else __import__('urllib.request').urlopen(x['url']).read())"
```

Omni may return a **top-level JSON array** of `{b64_json|url}` (not always `{"data":[...]}`). Always accept both shapes.
**Scenic prompts (any user language):** Prefer the classify `SCENE:` English line when present. Otherwise translate the user ask into one clear English diffusion sentence (place + subjects + **photorealistic photograph**). Only include aerial/top-down wording when the user asked for that viewpoint — never invent it. Prefer street-level / eye-level framing by default. Use official English place names — colloquial Saigon / Sài Gòn → Ho Chi Minh City (some providers falsely NSFW-block colloquial aliases). Safe-for-work daytime outdoor scenes; avoid close-up people unless the user asked for portraits. Always include: `photorealistic photograph, real camera photo, natural lighting, highly detailed, not cartoon, not anime, not illustration`. If the provider returns a tiny censor placeholder, strengthen the SCENE (SFW, official names, wider establishing shot) and retry once — do not invent hardcoded cityscape templates in code.

On Omni failure: one **media-out** failure line only. When the ask was primarily a **PDF/office file**, finish via **`file-gen`**.

## Local Pillow modes (not Omni diffusion)

Exact text posters only (not scenic diffusion or labeled dashboards):

| Need | Call |
|------|------|
| Exact text poster | `POST http://dispatcher:8090/v1/text-poster` |

Labeled metrics / weather pictures with facts on-image → **Omni combo image-gen** (`model=image-gen`) with facts baked into the English SCENE prompt (see `infographic-design` skill). Do **not** call retired `POST /v1/info-card` or `/v1/overlay`.

Do **not** call deprecated `POST http://dispatcher:8090/v1/image` for scenic generation.

## Output

Only `/opt/data/media/out/<safe-slug>.*` (webp/png/jpg).

## Related

- `multi-purpose`, `vision-ocr`, `video-gen`, `file-gen`
