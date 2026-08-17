# Case: profile upgrade / downgrade + existing / add / remove options

All tiers (Low / Medium / High) can move up or down. Runtime data stays on disk.
A change must **check current options**, **archive** (stamp), then apply. Undo is `restore`.

This is not a second Zalo SSE client. Keep `ENABLE_ZALO=1` as an **existing** flag through the cycle.

## Goal

- Existing options survive a tier change (Zalo, Traefik local, AV/sandbox/judge off).
- Adding an optional starts the service; removing it stops it (`--remove-orphans`).
- Downgrade High → Medium drops High-only containers (OpenBao, authz, SIEM) without wiping data.
- Upgrade Medium → High brings High-only services and Hermes×2 back.
- Unknown profile / unknown `ENABLE_*` is a **fail event** (non-zero, no stack dump).

## Preconditions

- Stack already deployed (lab: High + Zalo + edge).
- `.env` has secrets; `bash run.sh profile` prints current flags.
- Backup dir writable (`BACKUP_DIR`, default `/data/assistant/backups`).

## Steps

1. **Existing:** `bash run.sh profile` and `assistant_options_dump` (via `run.sh profile`). Record `ASSISTANT_PROFILE`, `ENABLE_ZALO`, sandbox/judge/AV, Traefik mode.
2. **Dry-run:** `bash run.sh switch-profile high --dry-run` and `bash run.sh add-components ENABLE_NOTIFY=1 --dry-run` — no stamp, no `.env` write.
3. **Archive (config at least):** set `BACKUP_COMPONENTS=config` for fast option stamps **or** full `bash run.sh backup`. Stamp must contain `config/profile-options.env` and `config/env.sealed`. `PRE_CHANGE` written on switch/add.
4. **Add:** `bash run.sh add-components ENABLE_NOTIFY=1 --no-up` then `bash run.sh up`. `ENABLE_NOTIFY=1` in `.env`; notify container up (High overlay).
5. **Remove:** `bash run.sh add-components ENABLE_NOTIFY=0 --no-up` then `bash run.sh up`. Notify absent; Zalo still on.
6. **Downgrade:** `bash run.sh switch-profile medium --no-up` then `bash run.sh up`. OpenBao/authz/SIEM gone; OCR/jobs/SearXNG and Zalo still present; `ENABLE_ZALO=1` still in `.env`.
7. **Upgrade:** `bash run.sh switch-profile high --no-up` then `bash run.sh up`. OpenBao/authz/security-manager back; Hermes×2; Zalo SSE still logged in (or zalo-watch restores without QR).
8. **Fail events:** `bash run.sh switch-profile bogus` → usage error; `bash run.sh add-components NOT_A_REAL_FLAG=1` → unknown option.

## Pass criteria

- Existing Zalo + isolation flags still set after the cycle (back on High).
- Add then remove notify observed in `docker ps`.
- Downgrade/upgrade service sets match the overlay (High-only absent on Medium).
- At least one archive stamp with `profile-options.env`.
- Fail events are short errors, not stack traces.
- Reports contain no hostnames, IPs, or account names.

## Fixtures

- Run A: add/remove `ENABLE_NOTIFY`; High ↔ Medium.
- Run B (pass 2 smoke): `--dry-run` only + `bash run.sh profile` (no tier change).
