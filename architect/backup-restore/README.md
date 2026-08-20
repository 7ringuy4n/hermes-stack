# backup-restore

## System architecture

| | |
|--|--|
| **Sits between** | Operator / timers ↔ Must stores + Hermes data |
| **Owns** | Stamp backup/restore/verify, worker/default expansion, post-restore heals |
| **Does not own** | Live app services (compose brings them back after restore) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Timers / run.sh</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>backup-restore</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">Postgres · Valkey · Qdrant · data</td>
  </tr>
</table>

## Purpose

Disaster recovery and runtime helpers: stamp backups of Must stores, restore, verify, and expand worker / component defaults from `.env`. Local stamps always; optional CloudDrive sync stays opt-in.

## Scope

Must layer for every install.

## What lives here

| Path | Function |
|------|----------|
| `ops.sh` | `backup` / `restore` / `verify` entry |
| `lib/profile.sh` | Compatibility shim to `workers.sh` |
| `lib/workers.sh` | `WORKER_*` / `ENABLE_*` → runtime flags |
| `lib/load-defaults.sh` | Load `docs/config/DEFAULTS.md` then `.env` |
| `lib/backup.sh` | Component backup/restore (Postgres, Qdrant, Valkey, Hermes data, …) |
| `lib/backup_qdrant.py` | Qdrant snapshot helpers |
| `lib/common.sh` | Shared bash helpers |

## Backup locations

| Setup | Where |
|---------|-------|
| Default | `/data/assistant/backups` |
| With CloudDrive | Same + optional CloudDrive sync |

Defaults: `BACKUP_DIR=/data/assistant/backups`, `HERMES_DATA_DIR=/data/assistant` (see [docs/config/DEFAULTS.md](../../docs/config/DEFAULTS.md)). Hermes tarball excludes `./backups`, `./replicas`, `./zalo_owner` / `./zalo_owner.lock`, and (unless opted in) `./lazy-packages` / `./media`.

## Timers (target)

| Job | Time | Layer | When |
|-----|------|-------|----------|
| auto-learn | 00:00 | tools/ingest | all installs |
| compact | 00:00 | memory hooks | when Media\|File worker is enabled |
| backup | 00:30 | this layer | all installs |

## Operator commands

```bash
bash run.sh backup              # stamp → $BACKUP_DIR (default /data/assistant/backups)
bash run.sh verify [stamp]      # manifest + live postgres/Valkey/qdrant probes
bash run.sh restore [stamp]     # restore stores then compose up (uses HERMES_REPLICAS)
bash run.sh migrate             # pack LATEST stamp for moving hosts
bash run.sh workers             # show current worker activation
bash run.sh add-components WORKER_MESSAGE=active ENABLE_ZALO=1
```

Stamps include `config/env.sealed` (full `.env`) and `config/profile-options.env` (non-secret runtime flags). Destroy, `add-components`, and `update` **backup then verify** and abort if verify fails. `switch-profile` is now a removed compatibility command that returns a worker hint.

### Restore behavior (important)

- Bring-up uses **Docker Compose** overlays under `docker/` (not `run.sh up` / first-setup), so restore does not re-run LLM bootstrap or wipe unrelated state unexpectedly.
- **Postgres:** `pg_dumpall --clean` restore skips `DROP`/`CREATE`/`ALTER ROLE` for the session DB user (`MEMORY_DB_USER`, default `hermes`) so the connected role is not dropped mid-restore. App containers that hold DB sessions are stopped first.
- **Qdrant (1.13+):** restores **per-collection** snapshots from the backup manifest. Full **storage** snapshot recover via HTTP is not supported (CLI/startup only); if the stamp has no collection snapshots (empty knowledge), recover is a clean skip.
- **Hermes×2:** stops/starts all containers matching `hermes`; compose `--scale hermes=$HERMES_REPLICAS`.
- **Zalo:** does not archive `zalo_owner` / `zalo_owner.lock` (runtime election). After restore, clears any leftover lock and runs `scripts/main/heal-zalo-sse.sh` so SSE re-attaches (Hermes container ids change on restore).
- **Schedules:** enables only timer units that exist on the host (missing units are skipped). Hermes user jobs live in `HERMES_DATA_DIR/cron/jobs.json` (shared). Backup copies that file plus `hermes-cron.tgz`. Restore writes them back, then `hermes-cron-share.sh` promotes leftover replica copies. Replica homes under `replicas/<container-id>/` are **not** the durable store (those ids change on destroy).

Full command index: [docs/02-commands.md](../../docs/02-commands.md).

## Tested successfully (lab)

Date: **2026-08-17** · Host: Ubuntu **24.04.4 LTS** · Workers: Message active, monitor off · `HERMES_REPLICAS=2` · Zalo logged in.

| Step | Result | Notes |
|------|--------|-------|
| Sync heal + `backup.sh` | **Pass** | LF-safe install under `/opt/assistant` |
| `bash run.sh backup` | **Pass** | Stamp `20260817_070637` under `/data/assistant/backups` |
| `bash run.sh verify <stamp>` | **Pass** | Manifest OK; live Postgres / Valkey / timers probed |
| Canary file in `HERMES_DATA_DIR` | **Pass** | Written before backup, removed, present again after restore |
| `bash run.sh restore <stamp>` | **Pass** | Datastore + Hermes data + post-restore `heal-zalo-sse.sh` |
| Pre-restore Zalo | `sseClients=0` | Confirmed silent-bot condition before heal |
| Post-restore Zalo | **Pass** | `loggedIn=true`, `sseClients=1` after heal; owner lock re-elected |
| Post-restore health | **Pass** | api-gateway OK; Hermes×2 up; `pg_isready`; Valkey `PONG`; Qdrant ready |
| Traefik after volume restore | **Fixed** | Volume restore stops Traefik; compose restore now includes `--profile traefik` (and peers) so edge returns |
| stack-watch vs Hermes×2 | **Fixed** | Watch previously ran `compose up` without `--scale`, collapsing replicas and dropping Zalo SSE; now preserves `HERMES_REPLICAS` |

Prior lab stamp: `20260816_195940`. Hardware: **4 vCPU / 16 GiB RAM / ~200 GB disk**, monitor off (~3 GiB idle). Enabling Grafana+Prometheus / Loki / all optionals adds RAM, disk, and CPU — [docs/HARDWARE.md](../../docs/HARDWARE.md) (**all optional features ~5 GiB RAM · ~40 GB disk · ~2 vCPU**).

## Related

- [host](../host/README.md)
- [docs/00-workers.md](../../docs/00-workers.md)
- [docs/HARDWARE.md](../../docs/HARDWARE.md)
