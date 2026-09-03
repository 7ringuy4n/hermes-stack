# Case 39 — Zalo Tn visual weather PDF

## Goal

User Tn asks for a live weather PDF with an attractive layout and a Ho Chi Minh City photo. Delivery must be a styled PDF (markdown + optional hero `IMAGE:`), not a SERP dump or create-sentence paste.

## Actor

Zalo user id `233767886566872937` (Tn) via bridge `/inject-event`.

## Steps

1. Ensure Media|File worker + office-file + Omni image-gen available.
2. Wait ≥45s after any prior LLM call (OmniRoute `maxWaitMs` queue).
3. Inject:

   > cập nhật dự báo thời tiết hồ chí minh hiện tại và điền vào pdf, layout phải thật bắt mắt có hình ảnh thành phố hồ chí minh

4. Wait up to 240s. Monitor Hermes + `com.hermes.zaloplugin` + dispatcher.

## Pass

- New PDF under `/data/assistant/media/out/`.
- Extracted text has a short title and labeled facts.
- No SERP chrome (site names, district nav, PM-only stubs, create-sentence title).
- No markdown table separator leftovers (`|------`).
- No hello/`/help` intro replacing the file.

## Fail / skip

- SERP dump or create sentence as body → FAIL (fix classify/file-gen + host gate).
- Rate-limit / quota on free models → SKIP and retest later.
- File delivered but no hero image: PASS only if fact cards/title layout are clean (image-gen may fail; skill allows omit IMAGE).

## Lab script

`test/scripts/zalo_tn_visual_weather_pdf_inject.py`
