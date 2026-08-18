# Case: Zalo special four (hello + weather image + fuel + weather video)

One lịch with **four English numbered tasks** must create **four jobs** at
tick time and deliver **four Zalo replies** (text and/or file) to the
logged-in bot’s thread. Isolated parallel sessions; no `/busy` tip.

## Fixture (English payload)

```text
every day at <HH:MM GMT+7>:
1. Send a hello greeting message.
2. Draw an image of Ho Chi Minh City based on the actual current weather.
3. Give a brief update of the latest E5 RON92 and E10 RON95 gasoline prices, in Vietnamese.
4. Draw a video of Ho Chi Minh City based on the actual current weather.
```

Vietnamese source of the same four intents (do not mix languages in one
lab run unless testing splitter):

```text
1. Gửi tin nhắn xin chào
2. Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.
3. Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất, bằng tiếng Việt.
4. Vẽ video Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.
```

Lab default: English list, clock **two minutes from now**, origin = current
Zalo login thread (`ZALO_HOME_CHANNEL` or last Zalo schedule origin).

## Why this is special

- Mixes **text**, **image-gen**, **web/search**, and **video** in one tick.
- Native Hermes `image_generation` may be off; image/video must use dispatcher
  / skills, not stop on “tool unavailable”.
- Parallel jobs on one thread used to merge into two replies. Isolated
  `thread::job::{id}` sessions must yield four deliveries.

## Steps (unit — no VPS)

```bash
python test/scripts/workflow_unit.py
python test/scripts/multi_request_unit.py
python test/scripts/workflow_turn_wait_unit.py
```

English 4-item list → `plan_instructions` length 4. Daily English list stays
**one** ingest payload (`ZALO_SCHEDULE_KEEP_WHOLE`).

## Steps (lab — current Zalo login)

```bash
python test/scripts/zalo_special_four_lab.py
```

1. Confirm plugin `loggedIn` and SSE owner.
2. Upsert schedule `case25_special_four` with the English list, `next_run_at`
   = two minutes from now (Asia/Ho_Chi_Minh).
3. Watch Hermes plugin logs + `wf.jobs` until four jobs complete (timeout
   `ZALO_WORKFLOW_TURN_TIMEOUT_S`, default 420s, plus parallel cap 4).
4. Pass if the origin thread receives **four** outbound replies (hello text,
   weather image, Vietnamese fuel text, video or a user-facing video error).

## Pass criteria

- Units PASS
- Tick creates 4 jobs (`sequential=false`)
- Four `[zalo] workflow job done` lines (isolated sessions)
- Four Zalo deliveries to the login thread
- No interrupt / First-time `/busy` copy
- Image path does not stop on native `image_generation` unavailable

## Fail events

- Only 1–2 Zalo replies → FAIL (session merge / late-file false complete)
- Four jobs COMPLETED in ~8s while the agent is still running → FAIL
- Image/video job stops at “tool unavailable” with no dispatcher attempt → FAIL
- `/busy` tip on Zalo → FAIL
- Replies go to the wrong thread → FAIL
