---
name: media-file
description: "Route file/OCR/media generation to the Media/File Worker (dispatcher, ComfyUI, OCR). Hermes does not pick an OCR engine."
---

# Media / file skill

Stack:

```text
Hermes → this skill → Media/File Worker
                     ├── ComfyUI (image/video)
                     ├── OCR / document extract
                     └── file create/convert
```

Classifier `skill_action` selects the worker operation. Do **not** implement `if PDF → OCR X` in application code.

| skill_action | Worker |
|---|---|
| `generate_media` | `POST http://dispatcher:8090/v1/image` or `/v1/video` (see `image-gen` / `video-gen`) |
| `process_file` / `process_image` | Ingest/OCR via `OCR_URL` / `INGEST_URL` — worker chooses the engine |
| `create_file` | `file-gen` / office skills |

## Must follow

1. Result-only after a file (`media-out`). No process chatter.
2. Output under `/opt/data/media/out/`.
3. ComfyUI is inside this worker, not OmniRouter.
4. Untrusted attachments: Security skill **before** this worker when required.

## Related

- `image-gen`, `video-gen`, `comfyui`, `file-gen`, `media-out`
- `security` — AV / YARA / sandbox / judge
