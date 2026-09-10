# Case: worker add / remove (existing options)

Workers are toggled with `WORKER_*=active|inactive` via `bash run.sh add-components`. Profile upgrade/downgrade (`switch-profile`) is removed.

Runtime data stays on disk. A change must **archive** (stamp), then apply. Undo is `restore`.

Keep `ENABLE_ZALO=1` as an **existing** flag through the cycle.

## Goal

- Existing options survive worker toggles (Zalo, Traefik local, AV/sandbox/judge off).
- Activating a worker starts its services; deactivating stops them (`--remove-orphans`).
- `bash run.sh switch-profile …` is a **fail event** (non-zero, message only).
- Unknown `WORKER_*` / unknown `ENABLE_*` is a **fail event** (non-zero, no stack dump).

## Preconditions

- Stack already deployed (lab: workers + Zalo + edge).
- `.env` has secrets; `bash run.sh workers` prints current activation.
- Backup dir writable (`BACKUP_DIR`, default `/data/assistant/backups`).

## Steps

1. **Existing:** `bash run.sh workers` and record `WORKER_*`, `ENABLE_ZALO`, sandbox/judge/AV, Traefik mode.
2. **Dry-run:** `bash run.sh add-components WORKER_NOTIFY=active --dry-run` — no stamp, no `.env` write.
3. **Backup + verify:** `bash run.sh backup` then `bash run.sh verify` must succeed before add (product `add-components` already gates this). Stamp must contain `config/profile-options.env` and `config/env.sealed`. `PRE_CHANGE` written on add.
4. **Add notify:** `bash run.sh add-components WORKER_NOTIFY=active --no-up` then `bash run.sh up`. `WORKER_NOTIFY=active` in `.env`; notify container up.
5. **Remove notify:** `bash run.sh add-components WORKER_NOTIFY=inactive --no-up` then `bash run.sh up`. Notify absent; Zalo still on.
6. **Fail events:** `bash run.sh switch-profile high` → removed message + non-zero; `bash run.sh add-components NOT_A_REAL_FLAG=1` → unknown option.

## Pass criteria

- Existing Zalo + isolation flags still set after the cycle.
- Add then remove notify observed in `docker ps`.
- `switch-profile` fails fast with the worker hint message.
- At least one archive stamp with `profile-options.env`.
- Fail events are short errors, not stack traces.
- Reports contain no hostnames, IPs, or account names.

## Fixtures

- Run A: add/remove `WORKER_NOTIFY` while Schedule/Media/Message stay active.
- Run B (pass 2 smoke): `--dry-run` only + `bash run.sh workers` (no worker change).
