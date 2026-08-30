# tools / ocr

## Purpose

Extract text from PDFs and images so Hermes and Media Worker skills can summarize
without a vision-capable LLM.

**Primary engine: PaddleOCR** (separate OCR container under the Media Worker
profile). Vision LLM is opt-in (`OCR_VISION=active`) and is never the first hop.

## Profile

Medium+ (`ENABLE_OCR=active` / `WORKER_MEDIA_FILE=active`). Off on Low.

## Flow

```
image / scanned PDF
        │
        ▼
   PaddleOCR (thread pool)
        │
   ┌────┴────┐
success    failure / empty
   │            │
   ▼            ▼
 text      tesseract / pymupdf
   │            │
   └─────┬──────┘
         ▼
   Hermes receives text
         ▼
   any LLM interprets
```

PDF with an embedded text layer still uses pymupdf directly (no raster OCR).

## Main functions

| Function | Detail |
|---|---|
| `POST /v1/ocr` | `{ path }` or `{ image_b64 }` → `{ ok, text, via }` |
| `via` | `paddle` \| `pymupdf` \| `tesseract` \| `9router` (only when `OCR_VISION=active`) |
| Empty scan | `{ ok:true, empty:true, text:"" }` — not a hard failure |

## Env

| Key | Default | Meaning |
|-----|---------|---------|
| `OCR_PADDLE` | `1` | Use PaddleOCR when wheels are installed |
| `OCR_VISION` | `0` | Opt-in vision LLM after paddle/tesseract |
| `OCR_PADDLE_MOBILE` | `1` | Prefer PP-OCRv5 mobile det/rec |
| `INSTALL_PADDLE` | `1` | Build-arg: install paddlepaddle + paddleocr |

## Related

- [ingest](../ingest/README.md)
- Media Worker dispatcher (`/v1/media/text` keyframe OCR also calls this service)
- `hermes/main/skills/core/worker-routing/SKILL.md`
