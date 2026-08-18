# workflow

Generic multi-request workflows. PostgreSQL is canonical; Valkey only delivers work.

Jobs are **instructions** (natural language), not hardcoded types like GET_FUEL_PRICE.

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

A schedule saved in the **same minute** as its clock (for example `13:54 GMT+7` at `13:54:20`) stays due **today** (120s grace). After it fires, the next run is the following day. If today's slot was missed and `next_run_at` already jumped to tomorrow, the ticker still catch-up fires once. Same-clock schedules for Zalo (`execute=hermes`) and Hermes API (`execute=hermes_http`) fire independently.

The workflow worker can also call Hermes over its internal HTTP API (`execute=hermes_http`) so non-Zalo requests are not coupled to the Zalo adapter.
