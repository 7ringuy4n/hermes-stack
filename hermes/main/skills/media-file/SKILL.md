---
name: media-file
description: "Conditional media/file router: still diffusion always Omni combo image-gen; vision reads use vision-ocr combo or hermes when inactive. Never silently bypass an active worker."
---

# Media / file skill

Forced stack policy:

```text
IF Media/File Worker ACTIVE:
  still-image diffusion → OmniRouter /images/generations model image-gen
  vision / office → vision-ocr combo (ingest/jobs/dispatcher/Zalo) + dispatcher office-file
ELSE:
  still-image diffusion → OmniRouter /images/generations model image-gen (same combo)
  vision / chat fallback → Omni/9Router combo hermes
  unsupported → explicit failure (never pretend success)
```

```text
Hermes → this skill
           ├── generate_media (always) → image-gen (Omni combo image-gen)
           ├── worker active
           │                     ├── vision-ocr (router-worker combo)
           │                     └── file create/convert
           └── worker inactive → combo hermes on Omni/9Router (vision/chat only; not still diffusion)
```

| skill_action | Active worker | Inactive worker |
|---|---|---|
| `generate_media` | OmniRouter `POST /v1/images/generations` model `image-gen` (skill HD `size`) | Same: Omni `model=image-gen` (never `hermes` for stills) |
| `process_file` / `process_image` | ingest/dispatcher vision-ocr combo | Omni/9Router multimodal `hermes` |
| `create_file` | `file-gen` / office via dispatcher | fail unless local office tools exist |

## Must follow

1. Result-only after a file (`media-out`).
2. Output under `/opt/data/media/out/`.
3. Preserve `thread_id` for delivery.
4. Video / music / audio / URL transcripts: refuse via `video-gen`.
5. Complex multi-panel briefs: `multi-purpose` (plan with `hermes`).

## Related

- `image-gen`, `vision-ocr`, `embedding`, `multi-purpose`, `video-gen`, `file-gen`, `media-out`
