---
name: video-gen
description: "Video generation is blocked on this stack — refuse via dispatcher policy (like video-summary). RESULT-ONLY (see media-out)."
---

# Video generation (refused)

Follow skill **`media-out`** (result only — no step chatter).

**Policy:** this stack does **not** generate synthetic video clips (same family as **`video-summary`** blocking YouTube/TikTok/Facebook fetch). Do **not** call `POST /v1/video`, manim, matplotlib, PIL frame loops, ffmpeg encode loops, or Comfy video workflows.

## Required (must)

1. **Do not** invent Python/video pipelines or install manim / pangocairo.
2. Ask dispatcher for the refuse message — **OmniRouter writes the user-facing text** (not hardcoded in the skill):

```bash
curl -sS -X POST http://dispatcher:8090/v1/video-policy-refuse \
  -H 'content-type: application/json' \
  -d '{"topic":"video_generate","context":"<verbatim user request>","language":"vi"}'
```

Or call `POST /v1/video-summary` when the user pasted a YouTube/TikTok/Facebook link and wants transcript/summary (`topic` is implicit — use the URL in `context` or `url`).

3. Reply with the JSON **`message`** field only. No step chatter, no approve, no chat_id / thread metadata.

## Alternatives (only when the user wanted visual output)

| Need | Route |
|------|--------|
| Still image / infographic / poster | **`image-gen`** → `POST /v1/image` |
| Office document | **`file-gen`** / **`documents`** |

## Related

- `media-out` — result-only delivery
- `image-gen` — supported still images
- `comfyui` — only when user named an explicit Comfy **image** workflow (not video)
