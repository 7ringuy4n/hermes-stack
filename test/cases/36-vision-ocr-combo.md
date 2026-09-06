# Case: vision-ocr combo for all image/PDF reads

## Goal

Images and scanned PDF pages are read by **combo vision-ocr** via router-worker
(`architect/lib/vision_ocr.py` in ingest, jobs, dispatcher, Zalo host). There is
no separate OCR container, no Paddle/tesseract path.

## Steps

1. Local: `python test/scripts/vision_ocr_policy_unit.py`
2. Local: `python test/scripts/ocr_refuse_unit.py`
3. Lab: with Media worker active, `POST ingest:8099/v1/extract` or dispatcher
   vision path on a still with known text → non-empty extract with sensible content.
4. Zalo DM: send a photo with visible text or a skyline ask (`hình gì đây`) → host
   describes the scene; never hallucinated unrelated content or “please upload image”.

## Pass criteria

- Both unit scripts print `PASS`.
- No `assistant-ocr-1` / `ocr:8091` container in `docker compose ps`.
- Zalo image-analyze returns a grounded description or the standard empty-line refuse.
