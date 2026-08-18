# workflow

Generic multi-request workflows. PostgreSQL is canonical; Valkey only delivers work.

Jobs are **instructions** (natural language), not hardcoded types like GET_FUEL_PRICE.

## Delivery policy (numbered lists)

A numbered list is **N jobs**, whether the user asked for it **now** or as a **lịch/schedule**. Immediate and scheduled use the same job engine. The schedule row is only the clock; at tick time it creates one workflow with one job per item.

**Each job may send its own Zalo (or Hermes) response.** There is no aggregator that folds four results into one bubble. Image files, fuel text, weather text, and a hello each go out as their own delivery. Job count is not tied to “one final message.”

Example:

```text
đặt lịch chạy lúc 15:50
1. Gửi tin nhắn xin chào
2. Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.
3. Cập nhật ngắn gọn giá xăng …
4. Cập nhật thời tiết hiện tại
```

becomes four jobs at 15:50, and the user should receive four replies (text and/or file), not two.

Zalo jobs run in **isolated parallel**: each job gets its own Hermes gateway session (`{thread}::job::{job_id}`) so `handle_message` does not queue later items as pending follow-ups. Sends are remapped to the real Zalo thread and serialized with a per-thread lock so four replies do not collide on the bridge. Cap: `ZALO_WORKFLOW_PARALLEL` (default 4). Each job still waits until **its** isolated session is idle before complete (timeout `ZALO_WORKFLOW_TURN_TIMEOUT_S`, default 420).

Hermes API numbered lists can stay sequential + aggregated (one HTTP response). That is a different delivery channel.

| Endpoint | Role |
|---|---|
| `POST /v1/workflows` | Create workflow + jobs + outbox |
| `GET /v1/workflows/{id}` | Status derived from job rows |
| `POST /v1/worker/claim` | Lease next job (`execute=hermes` or `record_only`) |
| `POST /v1/jobs/{id}/complete` / `fail` | Record attempt result |
| `POST /v1/schedules` | Durable cron that **creates jobs**, it does not run one LLM prompt |
| `POST /v1/schedules/tick` | Fire due schedules now (also runs every ~2s in-process) |
| `POST /v1/workflows/{id}/wait` | Wait briefly for terminal workflow state |

This service is available on all profiles. It is used by:

- Zalo compound lists and `!zalo schedule`
- direct Hermes API chat requests routed through the API gateway

For direct Hermes API requests, the gateway can turn:

- one chat message containing multiple numbered requests into one durable workflow
- a schedule-shaped request (`daily`, `hằng ngày`, `06:00 GMT+7`, etc.) into a stored schedule

A schedule saved in the **same minute** as its clock (for example `13:54 GMT+7` at `13:54:20`) stays due **today** (120s grace). **Cadence** (from the wording, overridable with `WORKFLOW_CADENCE_*` marker env vars):

| Cadence | After it fires |
|---------|----------------|
| `once` (default when the text has a clock but no daily/weekly/monthly/yearly word) | Row is **deleted** |
| `daily` | Next day, same clock |
| `weekly` | +7 days, same clock |
| `monthly` | Next month, same day/clock (clamped) |
| `yearly` | Next year, same date/clock |

If today's slot was missed and `next_run_at` already jumped to tomorrow, the ticker still catch-up fires once (same-minute grace). Same-clock schedules for Zalo (`execute=hermes`) and Hermes API (`execute=hermes_http`) fire independently.

Zalo `execute=hermes` jobs are claimed up to `ZALO_WORKFLOW_PARALLEL` at a time. Each job uses an isolated Hermes session, waits until that session is idle, heartbeats the lease, then late-sends any file. Completing after only the ~8s late-file window without isolation caused later items to be queued as pending follow-ups, so Zalo often received only the first one or two replies.

Tune `ZALO_WORKFLOW_TURN_TIMEOUT_S` (default 420) if an item such as image generation needs longer. The worker still marks a timed-out item completed-with-error so the rest of the list can run.

The workflow worker can also call Hermes over its internal HTTP API (`execute=hermes_http`) so non-Zalo requests are not coupled to the Zalo adapter.
