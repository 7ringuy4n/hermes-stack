# Case: image and video text is really read, never faked

## Goal

An image, a PDF page render, or a video frame must come back as text that exists in the
file. When the routed model has no vision, refusal detection drops blind chat replies —
a reply such as “please upload the image” must never be returned as extracted text, and
the watchdog must not bounce the media worker while a job is running.

## Steps

1. Local unit (no VPS): `python test/scripts/ocr_refuse_unit.py`
2. On the lab, make one still with known text and read via vision-ocr (ingest extract
   or dispatcher `/v1/media/text` keyframe path on a video still).
3. Video: `POST dispatcher:8090/v1/media/text` on an mp4 that has on-screen text →
   `frames_read > 0` and the on-screen string appears in `text`.
4. Audio with speech: same endpoint on an mp3 → non-empty `## Transcript`. A clip with no
   speech (tone only) must answer `ok: false` with `whisper returned empty transcript`,
   not an invented summary.
5. Watchdog: `journalctl -u assistant-stack-watch.service --since '-6 min'` while the media
   calls run, then `docker inspect -f '{{.RestartCount}}' dispatcher`.
6. Zalo DM: send the same image and the same video, then ask “tóm tắt nội dung”.

## Pass criteria

- `ocr_refuse_unit.py` prints `PASS` only.
- Vision read returns text that is actually in the picture when the combo has vision.
- `/v1/media/text` reports `frames_read > 0` for video, and on-screen text is present.
- stack-watch logs no `restart dispatcher` while dispatcher `/health` answers 200, and
  `RestartCount` is unchanged across at least three ticks.
- The Zalo reply summarizes what the file contains and never asks the user to resend it.
