---
name: schedule
description: "Create or delete a lịch via the Go schedule worker. Store when-to-run; deliver fire_text verbatim or process via Hermes."
---

# Schedule skill

Hermes does **not** run a cron worker. Persist a lịch with this skill, then stop.

## Create

`POST $SCHEDULE_URL/v1/schedules` (`SCHEDULE_URL` default `http://schedule-worker:8110`).

JSON body (deterministic fields from classifier JSON + **host-resolved** fire time):

- `schedule_form` — `once_at` | `once_after` | `recurring` (from classify)
- `delay_seconds` — integer seconds for `once_after` only (from classify). Host converts to `next_run_at` with the **runtime clock**. Never invent wall-clock time yourself.
- `cron_expr` — five-field cron for `once_at` / `recurring`. **Must be null/omitted for `once_after`** (host may derive a placeholder cron from resolved `next_run_at` for storage only).
- `cadence` — `once` / `daily` / `weekly` / `monthly` / `yearly`
- `timezone` — IANA zone (default `Asia/Ho_Chi_Minh`)
- `next_run_at` — RFC3339 UTC from **host/tool response only**. Classifier must leave this null. Do not compute now+offset in the model.
- `fire_text` — inner work only (`message` / `instructions` joined). **Never** the “đặt lịch lúc HH:MM” wrapper
- `text` — original inbound (audit only)
- `origin` / `context` — thread routing so the worker can inject back into the conversation
- `context.schedule_delivery` — `verbatim` (send body as-is) or `process` (Hermes runs skills)

### Delivery modes

| Mode | When | Fire behavior |
|---|---|---|
| **verbatim** | User asked to **send/post** a dictated body (`nhắn tôi` / `gửi` + `nội dung:`). Payload words are not skills. | Adapter sends `fire_text` **exactly** — no LLM paraphrase, no outbound noise filter |
| **process** | User asked to **do work** at a time (generate/search/weather/image/OCR), even if wrapped in `nội dung:` | Inject with `scheduleFire`; Hermes runs **split** skills; never dump the task list as the chat text |

## Delete / cancel

When classify returns `task_type=delete_schedule` / `skill_action=delete`:

- Resolve `target_channel` (if any) via **`zalo-context`** to the destination group thread id.
- Delete every schedule-worker row whose `origin`/`context` thread_id, chat_id, requester_id, or sender_id matches that group (or the current chat when no target is named).
- Confirm with a short count. Do not invent cron expressions.

Admin CLI (same host): `!zalo schedule remove group <tên nhóm>` / `!zalo schedule remove all <số>` also deletes Go worker rows (not only `cron/jobs.json`).

## Multiple clocks vs one fire

| Pattern | Store |
|---|---|
| One clock, multiple inner tasks (`đặt lịch 06:00: thơ, xăng, thời tiết`) | **One** schedule — `schedule_delivery=process`, `instructions[]` **split by skill** (not one blob) |
| Multiple clocks (`06:00 thời tiết` and `21:00 xăng` in one bubble) | **One lịch per clock** — adapter stores separate jobs |
| Relative delay (`1 phút nữa`, `sau 5 phút`) | **`once_after`** — `delay_seconds` only; host sets `next_run_at` |

Do not split a single-clock daily lịch into immediate async jobs.

## Deliver into a named Zalo group

When classify JSON includes `target_channel` (group **display name only**, no `zalo ` prefix — including “vào Zalo LC Group” → `LC group`), **always** resolve via skill **`zalo-context`** (`POST /v1/zalo/context` or `/v1/zalo/threads/find`) / zalo-api channel registry and rewrite schedule `origin.thread_id` to that group (requester stays `user_id`).

If the group is unknown:

- Tell admin to open that group and run `!zalo allow` / `!zalo label`, or DM `!zalo refresh`, then retry.
- **Do not** ask for a raw chat ID.
- **Do not** invent “send the request inside the group instead.”
- **Do not** substitute the current DM / “Home” chat.
- **Do not** invent a confirmation wait (no 60-minute hold). Fail fast with the allow/refresh instruction.

When a sole-admin `!zalo claim` exists, outbound delivery for that context uses `claim.claimed_thread_id`, never the admin `user_id` alone.

Confirm create with destination when cross-thread: `Đã lưu lịch … → nhóm <name>.`

## Must follow

1. Confirm **only after** the schedule service/tool returns success. Next run as `HH:MM DD/MM/YYYY` local from the **tool/host** `next_run_at` — never invent a clock. Include `→ nhóm …` when delivering elsewhere.
2. Do not call Hermes CLI cron (`cronjob` tool, `hermes cron`, `jobs.json`), or workflow `/v1/schedules/tick`.
3. Do not execute the inner task at create time.
4. User wording: **lịch** (Vietnamese) or **schedule** (English). Never **cron** in chat.
5. When due: **verbatim** jobs deliver body only; **process** jobs run skills. Never `Cronjob Response` / `job_id` footers.
6. Before naming a destination group, call **`zalo-context`**. Never guess.
7. Never claim a schedule was saved if the tool failed or was not called.

## Related

- `zalo-context` — resolve user/thread/claim ids (PostgreSQL via zalo-api)
- `core/scheduling` — how to behave when a due payload arrives
- Web search / media-file skills handle **process** fires
