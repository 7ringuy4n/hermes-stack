---
name: scheduling
description: "Execute a due lịch payload in local time (Asia/Ho_Chi_Minh). Do not persist a new schedule — the platform already stored it."
---

# Scheduling (local timezone)

Zalo and API Gateway persist lịch via LLM classify (`task_hint=schedule`) and the **Schedule skill → Go schedule worker**. This skill does **not** create Hermes CLI cron jobs and does **not** persist a new schedule when a due payload arrives.

## Must follow

1. **One clock:** `TZ=Asia/Ho_Chi_Minh` unless the user names another IANA zone.
2. **Do not persist a new lịch.** Do not call Hermes schedule/cron tools (`cronjob`, `hermes cron`, `jobs.json`), or invent a paraphrased cron prompt. If the inbound is a new lịch, the adapter already stored it.
3. **When a job is due:** do **only** the current instruction when the platform scoped the turn to one part. For a **single-fire multi-task** payload, complete **all** numbered items in order in that run. Do not wrap it as “Schedule a one-time task…”. Do not create another schedule for leftover items.
4. **Outbound:** send **only the finished answer** for the instruction. Never prefix with `Cronjob Response`, never append `(job_id: …)` or “To stop or manage this job…”.
5. **Today vs tomorrow** applies only if the platform asks you to compute a clock (tests/docs). Compare requested **local** time to **now** in that zone.
6. Confirm in one short line only when the platform did not already confirm. Next run as `HH:MM DD/MM/YYYY` (local). Name every numbered item. Do not invent a second timezone label.
7. **Immediate compound (not schedule):** one inbound bubble may become several turns over time — answer the current part only; do not merge later parts into this reply.
8. **User wording:** say **lịch** (Vietnamese) or **schedule** (English). Never **cron** / **cron job** in chat.

## Do not

- Say "tomorrow" when the target time today is still ahead of now.
- Append fake ⏱ footers or duplicate ICT labels.
- Offer `/help` or command catalogs when setting a schedule.
- Tell the user about `/busy`, interrupting a task, or first-time tips.
- Register multiple schedules for the same local HH:MM unless the user explicitly asked for separate times.
- Treat “không trích dẫn nguồn” as a knowledge-catalog lookup.
- Call the Hermes `cronjob` tool for Zalo lịch (use Schedule skill / schedule-worker only).

## Reference logic

Stack helper `architect/tools/schedule_tz.py` — `next_daily_run(hour, minute)` encodes the today/tomorrow rule for tests and docs.
