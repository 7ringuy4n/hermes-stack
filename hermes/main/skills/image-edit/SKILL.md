---
name: image-edit
description: "Edit one supplied image through OmniRoute combo image-edit. RESULT-ONLY (see media-out)."
---

# Image editing

Follow skill **`media-out`**. Require exactly one accessible source image unless the endpoint explicitly supports multiple references. Preserve identity, composition, and untouched regions unless the user asks to change them.

Call Model Router `POST /v1/images/edits` with requested combo model `image-edit`, the source image, and a concise edit instruction in the user's language. It prefers OmniRoute and may use only an operator-declared image-edit-capable fallback. Save the single completed image under `/opt/data/media/out/` and deliver it once.

Do not reinterpret an edit as text-to-image generation. Do not overwrite the source file. Do not expose credentials, provider members, internal paths, or operation identifiers.

## Related

- `image-gen` — create a new still
- `media-out` — result-only delivery
