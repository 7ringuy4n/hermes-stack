---
name: vision-ocr
description: "Read/describe images and scanned docs via combo vision-ocr on router-worker (hermes when Media worker inactive). RESULT-ONLY."
---

# Vision OCR

Follow skill **`media-out`** when delivering extracted text as the main result.

**Stack path:** router-worker `POST /v1/chat/completions` model **`vision-ocr`** (via `architect/lib/vision_ocr.py` in ingest, jobs, dispatcher, Zalo host).

Pipeline for **all** image/PDF docs:

1. PDF text layer (pymupdf) when present
2. **vision-ocr** combo (multimodal chat; router-worker when configured)

When Media worker is inactive, OCR_MODEL defaults to **`hermes`**.

Hermes must **not** invent OCR with PIL or base64 dumps. Host/services call `vision_read(path=...)` — no separate OCR container.

Reply with extracted plain text only.

## Related

- `image-gen`, `media-file`
