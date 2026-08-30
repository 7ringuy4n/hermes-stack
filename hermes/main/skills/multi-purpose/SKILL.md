---
name: multi-purpose
description: "Complex multi-part creative briefs (infographic layout, multi-panel visual + facts). Plan with chat combo hermes, then deliver via image-gen and/or file-gen. RESULT-ONLY."
---

# Multi-purpose visual briefs

When the user asks for a **structured multi-part visual** (infographic with several panels, icons, metrics, bilingual captions, layout constraints) — not a single scenic photo:

1. **Plan** with the default chat combo **`hermes`**
   - OmniRouter: `POST /v1/chat/completions` `model=hermes`
   - 9Router: same when enabled
2. **Deliver** using stack tools — never invent matplotlib/HTML screenshots:
   - Readable metrics / panels on a picture → **`image-gen`** `mode=info-card` (TITLE/SUBTITLE/ICON markers)
   - Scenic photo + small overlay facts → **`image-gen`** diffusion + `overlay[]`
   - PDF / office document → **`file-gen`**
3. Fetch live facts once via search when needed, then one generation call.

Follow **`media-out`**: result file or final answer only — no process chatter.

Do **not** use ComfyUI. Do **not** generate video/music/audio (see **`video-gen`** refuse).

## Related

- `image-gen` — still images
- `file-gen` — office files
- `core/answering` — chat-only answers when no file was asked
