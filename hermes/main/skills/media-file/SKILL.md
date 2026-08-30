---
name: media-file
description: "Conditional media/file router: active Media/File Worker wins; when inactive use router combo hermes. Never silently bypass an active worker."
---

# Media / file skill

Forced stack policy:

```text
IF Media/File Worker ACTIVE:
  image gen / OCR / vision / office → dispatcher / OCR (combos image-gen, vision-ocr)
ELSE:
  use router combo hermes for the same capabilities (Omni / 9Router chat or images APIs)
  unsupported → explicit failure (never pretend success)
```

```text
Hermes → this skill
           ├── worker active  → Media/File Worker
           │                     ├── image-gen (combo image-gen)
           │                     ├── vision-ocr (Paddle → combo vision-ocr)
           │                     └── file create/convert
           └── worker inactive → combo hermes on Omni/9Router
```

| skill_action | Active worker | Inactive worker |
|---|---|---|
| `generate_media` | `POST http://dispatcher:8090/v1/image` (`IMAGE_GEN_COMBO=image-gen`) | Omni/9Router with `model=hermes` |
| `process_file` / `process_image` | OCR/ingest (Paddle → `vision-ocr`) | Omni/9Router multimodal `hermes` |
| `create_file` | `file-gen` / office via dispatcher | fail unless local office tools exist |

## Must follow

1. Result-only after a file (`media-out`).
2. Output under `/opt/data/media/out/`.
3. Preserve `thread_id` for delivery.
4. Video / music / audio / URL transcripts: refuse via `video-gen`.
5. Complex multi-panel briefs: `multi-purpose` (plan with `hermes`).

## Related

- `image-gen`, `vision-ocr`, `embedding`, `multi-purpose`, `video-gen`, `file-gen`, `media-out`
