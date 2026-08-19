# Case: Zalo special four (hello + weather image + fuel + weather video)

One lịch with **four English numbered tasks** must create **four jobs** at
tick time and deliver **four Zalo replies** (text and/or file) to the
logged-in bot’s thread. Isolated parallel sessions; no `/busy` tip.

**Architect:** Input Secret Probe → LLM classify (`task_hint` + `instructions`)
→ Schedule Manager stores structured `context.plan` → tick creates one job per
instruction. `SECRET` is never a task type.

## Fixture (English payload)

```text
every day at <HH:MM GMT+7>:
1. Send a hello greeting message.
2. Draw an image of Ho Chi Minh City based on the actual current weather.
3. Give a brief update of the latest E5 RON92 and E10 RON95 gasoline prices, in Vietnamese.
4. Draw a video of Ho Chi Minh City based on the actual current weather.
```

Vietnamese source of the same four intents (do not mix languages in one lab run):

```text
1. Gửi tin nhắn xin chào
2. Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.
3. Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất, bằng tiếng Việt.
4. Vẽ video Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.
```

Lab default: English list, clock **two minutes from now**, origin = **current
Zalo admin DM only** (`zalo_admin_users.txt` sole admin uid, `thread_type=user`).
Do not send to groups or other allowed threads.

## Why this is special

- Mixes **text**, **image-gen**, **web/search**, and **video** in one tick.
- Native Hermes `image_generation` may be off; image/video must use dispatcher
  / skills, not stop on “tool unavailable”.
- Parallel jobs on one thread used to merge into two replies. Isolated
  `thread::job::{id}` sessions must yield four deliveries.
- Classification is **LLM** (`POST /v1/classify`), not split/join/regex in app code.

## Steps (unit — no VPS)

```bash
python test/scripts/llm_classify_unit.py
python test/scripts/workflow_unit.py
python test/scripts/multi_request_unit.py
python test/scripts/workflow_turn_wait_unit.py
python test/scripts/autosend_unit.py
python test/scripts/overlay_unit.py
python test/scripts/gateway_noise_unit.py
```

Mock LLM output for the English 4-item list has `instructions` length 4.
A daily payload is `task_hint=schedule` (kept whole on ingest). Tick uses
stored `context.plan.instructions`.

## Steps (lab — current Zalo login)

```bash
python test/scripts/zalo_special_four_lab.py
```

1. Confirm plugin `loggedIn` and SSE owner.
2. Upsert schedule `case25_special_four` with the English list, `next_run_at`
   = two minutes from now (Asia/Ho_Chi_Minh). Workflow classify must persist
   four instructions.
3. Watch Hermes plugin logs + `wf.jobs` until four jobs complete (timeout
   `ZALO_WORKFLOW_TURN_TIMEOUT_S`, default 420s, plus parallel cap 4).
4. Pass if the **admin DM** receives **four** outbound replies (hello text,
   weather image, Vietnamese fuel text, video or a user-facing video error).

## Pass criteria

- Units PASS
- Tick creates 4 jobs (`sequential=false`) from classified instructions
- Four `[zalo] workflow job done` lines (isolated sessions)
- Four Zalo deliveries to the **current admin DM**
- Replies to a group or non-admin thread → FAIL
- No interrupt / First-time `/busy` copy
- Image/video files are **sent** to the admin DM (`send-attachment`), not only written under `media/out`
- The **video** must be a **new** `.mp4` in the fire window **and** appear in `send-attachment path …mp4` (a leftover file from an earlier hour does not count)
- No `SECRET` task_hint

## Fail events

- Only 1–2 Zalo replies → FAIL (session merge / late-file false complete / classify collapsed to one instruction)
- Four jobs COMPLETED in ~8s while the agent is still running → FAIL
- Image/video job stops at “tool unavailable” with no dispatcher attempt → FAIL
- Media file exists in `media/out` but no `send-attachment` to the admin DM → FAIL
- Video job finishes with an old leftover `.mp4` (mtime before fire) and no new mp4 send → FAIL
- `send-attachment fail` for the new video (Zalo invalid parameter) with no successful remux send → FAIL
- `/busy` tip on Zalo → FAIL
- Replies go to the wrong thread → FAIL
