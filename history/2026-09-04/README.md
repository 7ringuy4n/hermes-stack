# 2026-09-04

## Omni requestQueue maxWaitMs

### Technical detail
- **Symptom:** Omni drops slow free-model jobs at `maxWaitMs=15000` (Bottleneck execution expiration; legacy name “queue budget”).
- **Root cause:** Default resilience setting; `/api/settings` does not persist nested `resilienceSettings`.
- **Fix:** `scripts/main/first-setup-omnirouter.py` → `ensure_request_queue_max_wait` → `PATCH /api/resilience` with `requestQueue.maxWaitMs` (env `OMNIROUTER_REQUEST_QUEUE_MAX_WAIT_MS`, default `600000`).
- **Verify:** `GET /api/resilience` shows raised `maxWaitMs`; chat smoke with free members no longer returns the 15s drop string.
