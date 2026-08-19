---
name: scheduling
description: "Execute a due lịch payload in local time (Asia/Ho_Chi_Minh). Do not persist a new schedule — the platform already stored it."
---

# Scheduling (local timezone)

Zalo and API Gateway persist lịch via LLM classify (`task_hint=schedule`) and the workflow Schedule Manager. This skill does **not** create Hermes CLI cron jobs.

## Must follow

1. **One clock:** `TZ=Asia/Ho_Chi_Minh` unless the user names another IANA zone.
2. **Do not persist a new lịch.** Do not call Hermes schedule/cron tools, `jobs.json`, or invent a paraphrased cron prompt. If the inbound is a new lịch, the adapter already stored it.
3. **When a job is due:** do **only** the current instruction. Do not wrap it as “Schedule a one-time task…”. Do not create another schedule for leftover items.
4. **Today vs tomorrow** applies only if the platform asks you to compute a clock (tests/docs). Compare requested **local** time to **now** in that zone.
5. Confirm in one short line only when the platform did not already confirm. Next run as `HH:MM DD/MM/YYYY` (local). Name every numbered item. Do not invent a second timezone label.
6. **When that schedule runs:** complete **all** numbered items in order in that run. After an image/file, continue the remaining items. Do not stop at media-out.
7. **User wording:** say **lịch** (Vietnamese) or **schedule** (English). Never **cron** / **cron job** in chat.

## Do not

- Say "tomorrow" when the target time today is still ahead of now.
- Append fake ⏱ footers or duplicate ICT labels.
- Offer `/help` or command catalogs when setting a schedule.
- Tell the user about `/busy`, interrupting a task, or first-time tips.
- Register multiple schedules for the same local HH:MM unless the user explicitly asked for separate times.
- Treat “không trích dẫn nguồn” as a knowledge-catalog lookup.

## Reference logic

Stack helper `architect/tools/schedule_tz.py` — `next_daily_run(hour, minute)` encodes the today/tomorrow rule for tests and docs.
