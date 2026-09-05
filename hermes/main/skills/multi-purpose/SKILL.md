---
name: multi-purpose
description: "Complex multi-part creative briefs (infographic layout, multi-panel visual + facts). Plan with chat combo hermes, then deliver via image-gen and/or file-gen. RESULT-ONLY."
---

# Multi-purpose visual briefs

When the user asks for a **structured multi-part visual** (infographic with several panels, icons, metrics, bilingual captions, layout constraints) — not a single scenic photo:

1. **Plan** with the default chat combo **`hermes`**
   - OmniRouter: `POST /v1/chat/completions` `model=hermes`
   - OmniRoute: same when enabled
2. **Deliver** using stack tools — never invent matplotlib/HTML screenshots:
   - Grounded information on a generated background → classifier `RENDER: composed-image`, Omni `image-gen`, then the model-authored `/v1/overlay` design
   - Pure visual with no information layer → Omni `/images/generations` model `image-gen`
   - PDF / office document → **`file-gen`**
3. Fetch live facts once via search when needed, then one generation call.

Do not prescribe fixed panels, labels, typography, colors, or placement. The
composition model adapts these choices to the user's complete brief and the
available grounded material.

Follow **`media-out`**: result file or final answer only — no process chatter.

Do **not** generate video/music/audio (see **`video-gen`** refuse).

## Related

- `image-gen` — still images
- `file-gen` — office files
- `core/answering` — chat-only answers when no file was asked
