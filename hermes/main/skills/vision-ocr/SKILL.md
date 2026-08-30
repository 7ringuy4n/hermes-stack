---
name: vision-ocr
description: "Read text from images and scanned docs via OCR (Paddle first, then vision combo vision-ocr; hermes when Media worker inactive). RESULT-ONLY."
---

# Vision OCR

Follow skill **`media-out`** when delivering extracted text as the main result.

**Stack path:** `POST http://ocr:8091/v1/ocr`

Pipeline for **all** image/PDF docs:

1. PDF text layer (pymupdf) when present
2. **PaddleOCR** (images + rasterized scanned PDF pages)
3. Vision LLM combo **`vision-ocr`** (Omni `/v1/chat/completions` multimodal; 9Router when enabled)
4. Tesseract last resort

When Media worker is inactive, OCR_MODEL defaults to **`hermes`**.

Hermes must **not** invent OCR with PIL or base64 dumps. Prefer the host OCR path:

```bash
curl -sS -X POST http://ocr:8091/v1/ocr \
  -H 'content-type: application/json' \
  -d '{"path":"/data/media/<relative-or-absolute>"}'
```

Reply with extracted plain text only.

## Related

- `image-gen`, `media-file`
