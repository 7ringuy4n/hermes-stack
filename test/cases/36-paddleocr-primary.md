# Case: PaddleOCR primary for images (Media Worker)

## Goal

Images and scanned PDF pages are read by **PaddleOCR first** inside the OCR
container (Media Worker boundary). Vision LLM is off by default. Hermes receives
plain text and any text-only model can summarize it.

## Steps

1. Local: `python test/scripts/paddle_ocr_unit.py`
2. `GET ocr:8091/health` → `primary=paddle`, `paddle=true`, `vision=false`
3. Still with known text `HOA DON 1250000 VND` → `POST /v1/ocr` returns that
   string with `via=paddle` (not `9router`)
4. Dispatcher keyframe OCR on a short mp4 with on-screen text still works
   (calls the same OCR service)
5. `OCR_VISION` remains `0` in compose unless explicitly enabled

## Pass criteria

- Unit prints `PASS`
- Health reports paddle available after first successful build
- No vision round trip in `docker logs ocr` for a normal screenshot
