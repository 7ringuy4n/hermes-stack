# Case 43 — OpenBao KV store, update propagation, scrub, up|update key fill

## Goal

Prove OpenBao remains the source of truth for API keys after seed/update, that plaintext exports are scrubbed, and that `run.sh` load-before-compose avoids empty compose keys after scrub.

## Checks

1. **Store** — KV `secret/assistant/api-keys` contains expected seed keys (e.g. `OMNIROUTER_API_KEY`) when OpenBao is enabled.
2. **Update** — Merging a new value into KV is readable on the next GET; obsolete retired keys are purged.
3. **Scrub** — After `scrub-plaintext-env`, `/data/assistant/.env.openbao` is gone and scrubbed keys in root `.env` have empty values (bootstrap token stays).
4. **Load** — `load-openbao-env` writes only a mode-0600 transient export; repository `.env` secret entries remain empty.
5. **Rotate** — `sync-openbao-env` imports a changed key into the current process, recreates its consumers with the new value, then removes the transient export without printing the value.
6. **Restore** — the lab restores the original KV value and recreates consumers again, so a test marker cannot leak into later operations.
7. **Pollinations** — `POLLINATIONS_API_KEY` is a seed/scrub key (not obsolete) when present.

## Scripts

- Unit: `test/scripts/openbao_common_unit.py`
- VPS lab: `test/scripts/openbao_kv_lab.py`

## Pass

All checks print `PASS` with no secrets in the report. Failures must not be marked pass.
