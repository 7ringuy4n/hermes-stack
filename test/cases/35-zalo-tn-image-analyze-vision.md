# Case: Zalo Tn image analyze via vision-ocr (inject)

Simulate user **Tn** (`233767886566872937`) sending a captioned photo through the
Zalo bridge (`POST /inject-event`), same path as a real phone message.

## Goal

Catch regressions where image-analyze replies with
`Không mô tả được ảnh — gửi lại giúp mình.` instead of a scene description.

## Preconditions

- Bridge logged in, Hermes SSE connected
- Tn in `zalo_admin_users.txt` (or `ZALO_TEST_USER_ID` set)
- Router combo `vision-ocr` healthy
- Latest Zalo plugin synced (`vision_ocr.py`, `adapter.py`, `attachment.py`)

## Steps

1. Local: `python test/scripts/zalo_tn_image_analyze_unit.py`
2. VPS: `python test/scripts/zalo_tn_image_analyze_inject.py`
3. Manual: send skyline photo + `hình gì đây` on Zalo Tn

## Pass criteria

| Check | Pass |
|-------|------|
| Unit stage/resolve for thread `233767886566872937` | yes |
| Inject creates `/opt/data/media/inbound/{id}/tn_image_probe.jpg` | yes |
| Hermes logs `attach_vision_read` or `attach_image_vision_reply` | yes |
| Outbound Zalo send within 120s | yes |
| Reply is **not** `Không mô tả được ảnh — gửi lại giúp mình.` | yes |

## Fail events

- `attach_vision_miss` — media path not visible in Hermes
- `attach_vision_empty` — router/vision-ocr returned empty
- `attach_image_vision_fail` — OCR noise or refused after retries
- `FAIL_VISION_DESCRIBE_LINE` — user-visible fail ack sent

## Notes

- Host media volume is usually `/data/assistant/media` (bind → `/opt/data/media` in container).
- Do not probe with `find /opt/data/media` on the **host** — use `/data/assistant/media` or `docker exec`.
