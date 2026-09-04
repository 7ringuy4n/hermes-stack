# 2026-09-04

## Omni maxWaitMs reset on update

### Technical detail
- **Symptom:** Jobs still dropped at `maxWaitMs=15000` after stack update.
- **Root cause:** Omni recreate resets resilience defaults; `run.sh update` did not re-apply `/api/resilience`.
- **Fix:** Default 24h clamp; force PATCH every setup/update; `run.sh update` → `update-omnirouter` (keeps combo members).
- **Verify:** Cookie-session `GET /api/resilience` shows `maxWaitMs=86400000`; live chat has no 15000 drop string.

## Obsolete env key cleanup

### Technical detail
- **Symptom:** Empty `ADMIN_API_TOKEN` and `WEB_BACKENDS=omni` lingered on VPS after combo-only search / OpenBao scrub.
- **Root cause:** Scrub cleared secret values but did not delete retired KEY lines.
- **Fix:** `cleanup-obsolete-env.py` + `OBSOLETE_ENV_KEYS`; scrub + load-openbao; filter OpenBao export; `.env.example` drops `WEB_BACKENDS`.
- **Verify:** Lab seeds retired pins then asserts they are gone; classifier/Omni smoke still HTTP 200.

## Omni requestQueue maxWaitMs

### Technical detail
- **Symptom:** Omni drops slow free-model jobs at `maxWaitMs=15000` (Bottleneck execution expiration; legacy name “queue budget”).
- **Root cause:** Default resilience setting; `/api/settings` does not persist nested `resilienceSettings`.
- **Fix:** `scripts/main/first-setup-omnirouter.py` → `ensure_request_queue_max_wait` → `PATCH /api/resilience` with `requestQueue.maxWaitMs` (env `OMNIROUTER_REQUEST_QUEUE_MAX_WAIT_MS`, default `600000`).
- **Verify:** `GET /api/resilience` shows raised `maxWaitMs`; chat smoke with free members no longer returns the 15s drop string.

## Hermes non-owner Zalo adapter ERROR

### Technical detail
- **Symptom:** Non-owner Hermes replica ERROR `Platform 'zalo' … adapter creation failed`.
- **Root cause:** Shared `config.yaml` still enabled `gateway.platforms.zalo` + `zalo-platform` after `ZALO_PLUGIN_URL` cleared.
- **Fix:** `hermes/main/docker/hermes-replica-entry.sh` → local config for non-owners with Zalo disabled; owner keeps shared symlink.
- **Verify:** After recreate, non-owner logs have no zalo adapter ERROR; Zalo bridge health still OK; owner keeps `zalo_url`.
