---
name: vision-ocr
description: "Read text from images via OCR service (Paddle first, then vision combo vision-ocr on Omni/9Router chat completions). RESULT-ONLY."
---

# Vision OCR

Follow skill **`media-out`** when delivering extracted text as the main result.

**Stack path:** dispatcher / ingest already call `POST http://ocr:8091/v1/ocr`.

Pipeline:

1. PaddleOCR (local) when available
2. Fallback / enrichment: vision LLM combo **`vision-ocr`**
   - OmniRouter: `POST /v1/chat/completions` with `model=vision-ocr` (multimodal)
   - 9Router: same OpenAI-compatible chat completions when enabled

Hermes must **not** invent OCR with regex, PIL, or base64 dumps. Prefer letting the host OCR path run; if you must call OCR yourself:

```bash
curl -sS -X POST http://ocr:8091/v1/ocr \
  -H 'content-type: application/json' \
  -d '{"path":"/data/media/<relative-or-absolute-image>"}'
```

Reply with extracted plain text only (user language). Do not claim vision models unless the OCR JSON says so.

## Related

- `image-gen` — create new images
- `media-file` — media worker routing
