---
name: schedule
description: "Create a lịch via the Go schedule worker. Store when-to-run only; Hermes processes the inner message when it is due."
---

# Schedule skill

Hermes does **not** run a cron worker. Persist a lịch with this skill, then stop.

## Create

`POST $SCHEDULE_URL/v1/schedules` (`SCHEDULE_URL` default `http://schedule-worker:8110`).

JSON body (deterministic fields from classifier JSON, not from parsing user prose):

- `cron_expr` — five-field cron from classify
- `cadence` — `once` / `daily` / `weekly` / `monthly` / `yearly`
- `timezone` — IANA zone (default `Asia/Ho_Chi_Minh`)
- `fire_text` — inner work only (`instructions` joined, or `message`). **Never** the “đặt lịch lúc HH:MM” wrapper
- `text` — original inbound (audit only)
- `origin` / `context` — thread routing so the worker can inject back into the conversation

The worker stores the row in SQLite, waits, and sends `fire_text` back through the Hermes inbound pipeline (`scheduleFire` protocol flag). Hermes classifies that inner message again and routes through skills.

## Multiple clocks vs one fire

| Pattern | Store |
|---|---|
| One clock, multiple inner tasks (`đặt lịch 06:00: chào, xăng, thời tiết`) | **One** schedule — `instructions[]` / `fire_text` contains all tasks for that fire |
| Multiple clocks (`06:00 thời tiết` and `21:00 xăng` in one bubble) | **One lịch per clock** — adapter stores separate jobs |

Do not split a single-clock daily lịch into immediate async jobs.

## Deliver into a named Zalo group

When classify JSON includes `target_channel` (group display name), **always** resolve via skill **`zalo-context`** (`POST /v1/zalo/context` or `/v1/zalo/threads/find`) / zalo-api channel registry and rewrite schedule `origin.thread_id` to that group (requester stays `user_id`).

If the group is unknown:

- Tell admin to open that group and run `!zalo allow` / `!zalo label`, or DM `!zalo refresh`, then retry.
- **Do not** ask for a raw chat ID.
- **Do not** invent “send the request inside the group instead.”
- **Do not** substitute the current DM / “Home” chat.
- **Do not** invent a confirmation wait (no 60-minute hold). Fail fast with the allow/refresh instruction.

When a sole-admin `!zalo claim` exists, outbound delivery for that context uses `claim.claimed_thread_id`, never the admin `user_id` alone.

## Must follow

1. Confirm in one short line. Next run as `HH:MM DD/MM/YYYY` local. Do not invent a second timezone label.
2. Do not call Hermes CLI cron (`cronjob` tool, `hermes cron`, `jobs.json`), or workflow `/v1/schedules/tick`.
3. Do not execute the inner task at create time.
4. User wording: **lịch** (Vietnamese) or **schedule** (English). Never **cron** in chat.
5. When the due payload runs, the delivered chat must be **body only** — never `Cronjob Response` / `job_id` / stop-reminder footers.
6. Before naming a destination group, call **`zalo-context`**. Never guess.

## Related

- `zalo-context` — resolve user/thread/claim ids (PostgreSQL via zalo-api)
- `core/scheduling` — how to behave when a due payload arrives
- Web search / media-file skills handle the inner work after fire
