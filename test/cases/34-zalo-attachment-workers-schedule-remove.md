# Case: attachment workers, mixed pack, compound split, schedule remove

## Goal

Every inbound Zalo file reaches a worker that can read it, follow-up turns reuse
that text, compound requests fan out, and admins can bulk-remove schedules.

## Steps

1. Local units (no VPS):
   - `python test/scripts/zalo_attachment_unit.py`
   - `python test/scripts/schedule_crud_unit.py`
   - `python test/scripts/multi_request_unit.py`
   - `python test/scripts/inbound_queue_unit.py`
   - `python test/scripts/web_search_backends_unit.py`
2. Zalo DM — one file per turn:
   - `.txt` (`123`) → summary in the same turn, no “paste the content” ask
   - image with text → OCR text summarized, not a generic photo description
   - `.pdf` → bullet summary even when learn-approve also notifies the admin
   - `.docx` / `.xlsx` / `.pptx` / `.csv` → summary in the same turn (approval must not block the reply)
   - `.mp4` / `.mp3` → transcript or keyframe text; if none, one honest line, never a fake summary
3. Send a mixed pack (txt + md + docx + xlsx + mp3 + mp4 + image) back to back, then ask
   “tóm tắt các file vừa gửi” → answer cites several files from recall memory, nothing dropped by the FIFO.
4. Ask “Tạo file text chứa 1 rồi gửi cho tôi” → `one.txt` arrives as an attachment.
5. Compound, no numbering: `gửi tin chào buổi sáng và tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất
   kèm theo thông tin thời tiết Hồ Chí Minh hiện tại` → 3 parts, both fuel grades in one part.
6. Admin schedule remove in a group:
   - `!zalo schedule remove 1 3 5`, `!zalo schedule remove 1-3`
   - `!zalo schedule remove group <group name>` and `… group <group name> 1-2`
   - `!zalo schedule remove all`
7. `POST /v1/search` on `model-router:8096` answers; the same path on `dispatcher:8090` is gone.

## Pass criteria

- Every unit script prints `PASS` only.
- No reply asks the user to paste or re-upload content that a worker already extracted.
- `docker logs dispatcher` shows no health-probe flap while OCR/media jobs run.
- Schedule removal deletes from both `cron/jobs.json` and the workflow service, and the
  reply lists what went away (count + labels, capped preview).
- Group removal on an unknown group name answers with the “unknown group” message, not a stack trace.
