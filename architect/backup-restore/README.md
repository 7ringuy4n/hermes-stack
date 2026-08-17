# backup-restore

## Purpose

Disaster recovery and profile helpers: stamp backups of Must stores, restore, verify, and expand `ASSISTANT_PROFILE` into optional flags. Local stamps always; High may sync to CloudDrive.

## Profile

Must (all profiles).

## What lives here

| Path | Function |
|------|----------|
| `ops.sh` | `backup` / `restore` / `verify` entry |
| `lib/profile.sh` | `ASSISTANT_PROFILE` → optional `ENABLE_*` |
| `lib/load-defaults.sh` | Load `docs/config/DEFAULTS.md` then `.env` |
| `lib/backup.sh` | Component backup/restore (Postgres, Qdrant, Valkey, Hermes data, …) |
| `lib/backup_qdrant.py` | Qdrant snapshot helpers |
| `lib/common.sh` | Shared bash helpers |

## Backup locations

| Profile | Where |
|---------|-------|
| Low / Medium | `/data/assistant/backups` |
| High | Same + optional CloudDrive sync |

Defaults: `BACKUP_DIR=/data/assistant/backups`, `HERMES_DATA_DIR=/data/assistant` (see [docs/config/DEFAULTS.md](../../docs/config/DEFAULTS.md)). Hermes tarball excludes `./backups`, `./replicas`, `./zalo_owner` / `./zalo_owner.lock`, and (unless opted in) `./lazy-packages` / `./media`.

## Timers (target)

| Job | Time | Layer | Profiles |
|-----|------|-------|----------|
| auto-learn | 00:00 | tools/ingest | all |
| compact | 00:00 | memory hooks | medium+ |
| backup | 00:30 | this layer | all |

## Operator commands

```bash
bash run.sh backup              # stamp → $BACKUP_DIR (default /data/assistant/backups)
bash run.sh verify [stamp]      # manifest + live postgres/redis/qdrant probes
bash run.sh restore [stamp]     # restore stores then compose up (uses HERMES_REPLICAS)
bash run.sh migrate             # pack LATEST stamp for moving hosts
```

### Restore behavior (important)

- Bring-up uses **Docker Compose** overlays under `docker/` (not `run.sh up` / first-setup), so restore does not re-run LLM bootstrap or wipe unrelated state unexpectedly.
- **Postgres:** `pg_dumpall --clean` restore skips `DROP`/`CREATE`/`ALTER ROLE` for the session DB user (`MEMORY_DB_USER`, default `hermes`) so the connected role is not dropped mid-restore. App containers that hold DB sessions are stopped first.
- **Qdrant (1.13+):** restores **per-collection** snapshots from the backup manifest. Full **storage** snapshot recover via HTTP is not supported (CLI/startup only); if the stamp has no collection snapshots (empty knowledge), recover is a clean skip.
- **Hermes×2:** stops/starts all containers matching `hermes`; compose `--scale hermes=$HERMES_REPLICAS`.
- **Zalo:** does not archive `zalo_owner` / `zalo_owner.lock` (runtime election). After restore, clears any leftover lock and runs `scripts/main/heal-zalo-sse.sh` so SSE re-attaches (Hermes container ids change on restore).
- **Schedules:** enables only timer units that exist on the host (missing units are skipped).

Full command index: [docs/02-commands.md](../../docs/02-commands.md).

## Tested successfully (lab)

Date: **2026-08-17** · Host: Ubuntu **24.04.4 LTS** · Profile: **High** · `HERMES_REPLICAS=2` · monitor off · Zalo logged in.

| Step | Result | Notes |
|------|--------|-------|
| Sync heal + `backup.sh` | **Pass** | LF-safe install under `/opt/assistant` |
| `bash run.sh backup` | **Pass** | Stamp `20260817_070637` under `/data/assistant/backups` |
| `bash run.sh verify <stamp>` | **Pass** | Manifest OK; live Postgres / Valkey / timers probed |
| Canary file in `HERMES_DATA_DIR` | **Pass** | Written before backup, removed, present again after restore |
| `bash run.sh restore <stamp>` | **Pass** | Datastore + Hermes data + post-restore `heal-zalo-sse.sh` |
| Pre-restore Zalo | `sseClients=0` | Confirmed silent-bot condition before heal |
| Post-restore Zalo | **Pass** | `loggedIn=true`, `sseClients=1` after heal; owner lock re-elected |
| Post-restore health | **Pass** | api-gateway OK; Hermes×2 up; `pg_isready`; Redis `PONG`; Qdrant ready |
| Traefik after volume restore | **Fixed** | Volume restore stops Traefik; compose restore now includes `--profile traefik` (and peers) so edge returns |
| stack-watch vs Hermes×2 | **Fixed** | Watch previously ran `compose up` without `--scale`, collapsing replicas and dropping Zalo SSE; now preserves `HERMES_REPLICAS` |

Prior lab stamp: `20260816_195940`. Hardware: **4 vCPU / 16 GiB RAM / ~200 GB disk** (see [docs/HARDWARE.md](../../docs/HARDWARE.md)).

## Related

- [host](../host/README.md)
- [docs/00-profiles.md](../../docs/00-profiles.md)
- [docs/HARDWARE.md](../../docs/HARDWARE.md)
