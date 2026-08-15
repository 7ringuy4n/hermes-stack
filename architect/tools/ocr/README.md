# tools / ocr

## Purpose

Extract text from PDFs and images so ingest and upload skills can index or summarize. Uses vision/upstream then fallbacks (e.g. pymupdf/tesseract) inside the service.

## Profile

Medium+ (`ENABLE_OCR=1`). Off on Low.

## Main functions

| Function | Detail |
|---|---|
| `POST /v1/ocr` | `{ path }` or image → text/markdown |
| Fail soft | Empty text → caller reports "could not read", no invented quotes |

## Related

- [ingest](../ingest/README.md)  
- [hermes/main/skills/upload](../../../hermes/main/skills/upload/SKILL.md)
