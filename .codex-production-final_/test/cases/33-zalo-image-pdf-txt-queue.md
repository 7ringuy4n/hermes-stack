# Case: Zalo image / PDF summary / txt send / queue

## Goal

Realistic Zalo media flows after Security Worker AV (no adapter AV cheat).

## Steps

1. Send a photo with no caption → bot describes the image (never “please describe the photo”)
2. Send a PDF → short bullet summary in the same turn; learn-approve may also notify admin
3. While a long reply is running, send another chat → queued ack; second reply after first finishes (per-thread FIFO)
4. “Tạo file text chứa dung 1 rồi gửi cho tôi” → user receives `1` (file or text fallback if Zalo rejects `.txt` attachment)

## Pass criteria

- OCR for PDF does not 404 (`/data/media/inbound/...`)
- `send-attachment` invalid-param for `.txt` falls back to message body
- Queue announces when `len > 1`
