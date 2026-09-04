# 2026-09-04

## 18:10 — Privileged OpenBao refresh preserves runtime ownership

### Symptom

Running the OpenBao export refresh with elevated privileges could leave the generated compose secret export owned by root, preventing later stack operations by the normal runtime-data owner.

### Root cause

The loader enforced secret file permissions after writing but did not restore ownership when the process effective user differed from the owner of the persistent data directory.

### Technical detail

- **Function:** `scripts/main/load-openbao-env.py::match_export_owner()` (`L204–L224`) applies the data directory UID/GID and falls back to the invoking sudo user only when directory stat/chown fails.
- **Call site:** `scripts/main/load-openbao-env.py:L264–L274` writes `.env.openbao`, keeps mode `0600`, then restores ownership before refilling compose keys.
- **Ownership:** `.env.openbao` changes from a possible privileged-process owner to the UID/GID of `ASSISTANT_DATA_DIR`; `SUDO_USER` is a guarded fallback, not a configured owner override.
- **Key:** file contents and OpenBao key names are unchanged; this fix changes only filesystem owner metadata while retaining permission value `0o600`.

### AI decision

Ownership is derived from the existing data directory because it is the durable source of truth for the deployment operator. Hard-coding a username, relaxing permissions, or applying a one-off VPS chown was rejected as environment-specific and non-durable.

### Fix (core)

- Added owner restoration to the core OpenBao export path.
- Added a platform-safe unit using the actual data-directory stat values and a mocked chown call.
- Verified a privileged loader run on the VPS keeps both the host env and generated export owned by the stack operator with restrictive modes.

### Todo list

- [x] Reproduce/inspect ownership after a privileged refresh.
- [x] Implement ownership restoration in the source loader.
- [x] Add unit coverage without requiring root privileges.
- [x] Run the unit locally and on the VPS.
- [x] Run the real loader with sudo and verify owner/mode afterward.

### Prevent recurrence

`test/scripts/openbao_common_unit.py:L48–L62` asserts that `match_export_owner()` calls chown with the data-directory UID/GID. Future privileged refresh paths must continue using the core loader rather than shell ownership patches.

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
