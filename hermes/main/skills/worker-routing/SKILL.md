---
name: worker-routing
description: "Route Hermes capabilities to specialized workers. No generic Dispatcher."
---

# Worker Routing Skill

Hermes understands the request and chooses a capability. This skill maps capability → specialized worker. There is **no** second orchestration layer (generic Dispatcher is deprecated).

## Flow

```text
User → Gateway → Hermes → Worker Routing → Security Worker (when required) → Worker → (outbound Security) → Channel
```

Async / long-running:

```text
Hermes → Security Worker → Queue → Worker
```

The queue is infrastructure only — not a router.

## Routing table

| Capability | Worker | How Hermes invokes |
|------------|--------|--------------------|
| Schedule create / list / history | Schedule Worker | `SCHEDULE_URL` (`POST /v1/schedules`, `GET /v1/schedules/history`) |
| OCR / files / image-video gen / convert | Media Worker | Media skills + OCR/Jobs URLs (not Dispatcher for new work) |
| Technical RAG ingest / retrieve | Knowledge Worker | Ingest + Qdrant via knowledge skill |
| Web research | Search backends / SearXNG | `web-search` skill |
| Channel admin / allowlists | Message Worker (zalo-api) | `!zalo` / ZALO_API_URL |
| Notifications | Notification Worker | NOTIFY_URL |
| Secrets / AV / DLP / path policy | Security Worker | When enabled — fail closed if required but down |

## Schedule (must be fast to ack)

1. Classify returns `task_hint=schedule` + cron + `target_channel` (display name, including “vào Zalo LC Group”) + `schedule_delivery`.
2. Persist via Schedule Worker immediately (no Hermes LLM for the store). Do not run inner skills at create time.
3. Ack the user with next run + schedule id (+ `→ nhóm …` when delivering elsewhere).
4. When due, Schedule Worker injects `fire_text` with `scheduleFire=true` (and `scheduleDelivery`) into the target thread (group or DM).
5. **verbatim**: host sends body as-is (dictated send-text, even if payload words look like skills). **process**: Hermes runs **split** skills (search/media/…). Mention-gate / rate-limit / inflight **must not** drop `scheduleFire`. `!zalo` admin must not wait behind a stuck media turn.

## Security

Security Worker decides allow / deny / sanitize — **not** which worker runs.

If Security is required and unavailable → **DENY** (fail closed). Never bypass.

## Dispatcher

Do not add new features to Dispatcher. Prefer Media Worker / Schedule Worker / skills directly. Health flaps on Dispatcher must not spam CRITICAL alerts (`HEALTH_FAIL_STREAK`).
