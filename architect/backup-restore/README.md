# backup-restore

## Purpose

Disaster recovery and profile helpers: stamp backups of Must stores, restore, verify, and expand `ASSISTANT_PROFILE` into optional flags. Local stamps always; High may sync to CloudDrive.

## Profile

Must (all profiles).

## What lives here

| Path | Function |
|---|---|
| `ops.sh` | `backup` / `restore` / `verify` entry |
| `lib/profile.sh` | `ASSISTANT_PROFILE` → optional `ENABLE_*` |
| `lib/load-defaults.sh` | Load `docs/config/DEFAULTS.md` then `.env` |
| `lib/backup.sh` | Component backup/restore (Postgres, Qdrant, Valkey, Hermes data, …) |
| `lib/backup_qdrant.py` | Qdrant snapshot helpers |
| `lib/common.sh` | Shared bash helpers |

## Backup locations

| Profile | Where |
|---|---|
| Low / Medium | `/data/assistant/backups` |
| High | Same + optional CloudDrive sync |

## Timers (target)

| Job | Time | Layer | Profiles |
|---|---|---|---|
| auto-learn | 00:00 | tools/ingest | all |
| compact | 00:00 | memory hooks | medium+ |
| backup | 00:30 | this layer | all |

Operator commands: [docs/02-commands.md](../../docs/02-commands.md) — `bash run.sh backup|restore|verify|migrate|auto-learn|compact|optimize-memory|install-timers|…`.

## Related

- [host](../host/README.md)  
- [docs/00-profiles.md](../../docs/00-profiles.md)
