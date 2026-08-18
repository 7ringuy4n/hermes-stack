---
name: scheduling
description: "Daily schedules and recurring reminders in local time (Asia/Ho_Chi_Minh). Use when the user asks to set a recurring alert, reminder, or schedule at a clock time."
---

# Scheduling (local timezone)

## Must follow

1. **One clock:** `TZ=Asia/Ho_Chi_Minh` unless the user names another IANA zone.
2. **Today vs tomorrow:** compare the requested **local** time to **now** in that zone.
   - If the requested time is **still in the future today** (including a few minutes ahead), schedule **today** — not tomorrow.
   - Example: now `05:58`, user asks daily `06:00` → **today 06:00**, then every day.
   - Only use **tomorrow** when today's slot has **already passed**.
3. Confirm in one short line: next run as `HH:MM DD/MM/YYYY` (local). If the payload has several numbered items, name **all** of them in that confirm (wakeup + image + prices), not only the first. Do not invent a second timezone label.
4. Use Hermes built-in schedule tools for persistence (internal CLI only). Do not mention internal job ids, `cron_*` session names, or `job_id:` in user-facing text.
5. On schedule tool failure: reply only `Phiên làm việc bị gián đạn, vui lòng thử lại sau` (or English equivalent). No stack trace, no architect/feature names.
6. **One lịch, every item:** if the user lists several numbered tasks for the same clock (wakeup + image + prices, etc.), create **one** recurring schedule whose payload is the **full list**. Do not create one schedule per line — parallel runs at the same time interrupt each other and drop later tasks.
7. **When that schedule runs:** complete **all** numbered items in order in that run. After an image/file, continue the remaining items. Do not stop at media-out. Do not skip a later item because an earlier item already replied.
8. **User wording:** say **lịch** (Vietnamese) or **schedule** (English). Never **cron** / **cron job** in chat.

## Do not

- Say "tomorrow" when the target time today is still ahead of now.
- Append fake ⏱ footers or duplicate ICT labels.
- Offer `/help` or command catalogs when setting a schedule.
- Tell the user about `/busy`, interrupting a task, or first-time tips.
- Register multiple schedules for the same local HH:MM unless the user explicitly asked for separate times.

## Reference logic

Stack helper `architect/tools/schedule_tz.py` — `next_daily_run(hour, minute)` encodes the today/tomorrow rule for tests and docs.
