---
name: vision-ocr
description: "Read/describe images and scanned docs via combo vision-ocr on model-router (hermes when Media worker inactive). RESULT-ONLY."
---

# Vision OCR

Follow skill **`media-out`** when delivering extracted text as the main result.

**Stack path:** model-router `POST /v1/chat/completions` requested model **`vision-ocr`** (via `architect/lib/vision_ocr.py` in ingest, jobs, dispatcher, Zalo host). Model Router prefers the OmniRoute combo and may use only an operator-declared vision-capable fallback model.

Pipeline for **all** image/PDF docs:

1. PDF text layer (pymupdf) when present
2. **vision-ocr** combo (multimodal chat; model-router when configured)

Hermes must **not** invent OCR with PIL or base64 dumps. Host/services call `vision_read(path=...)` — no separate OCR container.

Reply with extracted plain text only.

## Related

- `image-gen`, `media-file`
