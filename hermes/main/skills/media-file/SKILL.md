---
name: media-file
description: "Conditional media/file router: active Media/File Worker wins; otherwise supported OmniRouter models. Never silently bypass an active worker."
---

# Media / file skill

Forced stack policy (overrides conflicting legacy skill text):

```text
IF Media/File Worker ACTIVE:
  image gen / OCR / vision / office / conversion → Media/File Worker (dispatcher)
ELSE:
  use supported OmniRouter-backed models for the same capabilities
  unsupported → explicit failure (never pretend success)
```

```text
Hermes → this skill
           ├── worker active  → Media/File Worker
           │                     ├── ComfyUI (image)
           │                     ├── OCR / document extract
           │                     └── file create/convert
           └── worker inactive → OmniRouter capability models
```

Classifier `skill_action` selects the operation. Do **not** hard-code engine names in app code.

| skill_action | Active worker | Inactive worker |
|---|---|---|
| `generate_media` | `POST http://dispatcher:8090/v1/image` | OmniRouter image model (when configured) |
| `process_file` / `process_image` | OCR/ingest worker URLs | OmniRouter OCR/vision model when available |
| `create_file` | `file-gen` / office via dispatcher | local office tools only when available; else OmniRouter-supported path or fail |

## Must follow

1. Result-only after a file (`media-out`). No process chatter.
2. Output under `/opt/data/media/out/`.
3. Preserve `thread_id` for delivery — never replace with `user_id` (`zalo-context` / claim).
4. Preserve `correlation_id` / `execution_id` when present.
5. Untrusted attachments: Security Worker **before** this skill when Security is active.
6. Video: refuse via `video-gen` policy (no silent Comfy video).

## Related

- `image-gen`, `video-gen`, `comfyui`, `file-gen`, `media-out`, `zalo-context`
- `security` — AV / YARA / sandbox / inbound message-check
