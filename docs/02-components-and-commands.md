# 02 — Components and commands

## Deployed component map

| Layer | Current components |
|---|---|
| Agent | Hermes replicas, skills, per-replica runtime homes |
| Request routing | model-router → OmniRoute priority combos; omni-attribution |
| State | PostgreSQL, Valkey, Qdrant, `/data/assistant` |
| Knowledge | ingest → embedding combo → Qdrant |
| Edge | Traefik and API Gateway in local/VPN mode by default |
| Schedule worker | schedule-worker and timed Zalo delivery |
| Media/File worker | dispatcher, jobs, jobs-worker, SearXNG |
| Message worker | zalo-proxy, zalo-api, host Zalo bridge |
| Security worker | OpenBao, security-manager, authz, SIEM, policy; optional AV |
| Monitor worker | Prometheus, Grafana, Loki, Alloy |
| Notify worker | notify and alert-watch |

Image generation, image edit, vision analysis, web search, and embedding are
named OmniRoute combo capabilities. They are not local OCR/Comfy/video
containers. `video-gen` and `video-edit` are not supported.

## Command matrix

Run all commands from the repository root.

| Command | Effect |
|---|---|
| `bash run.sh up` | Start/reconcile core and enabled workers. |
| `bash run.sh down` | Stop compose services without deleting data. |
| `bash run.sh destroy` | Back up and verify, then remove this project's containers and networks; keep volumes and `/data/assistant`. |
| `bash run.sh update` | Back up and verify, rebuild/reconcile, preserve OmniRoute combo configuration, and clean supported retired env keys. |
| `bash run.sh ps` / `logs [service]` | Inspect runtime state/logs. |
| `bash run.sh workers` | Show effective worker and core flags. |
| `bash run.sh install NAME…` | Enable workers after backup/verification. |
| `bash run.sh uninstall NAME…` | Disable workers after backup/verification. |
| `bash run.sh backup` / `verify` / `restore` | Disaster-recovery stamp lifecycle. |
| `bash run.sh auto-learn` / `learn-status` | Knowledge indexing. |
| `bash run.sh compact` / `optimize-memory` | Knowledge/memory maintenance using embedding. |
| `bash run.sh install-timers` | Install host timers and enabled-worker watches. |
| `bash run.sh first-setup-omnirouter` | Setup-only OmniRoute initialization; no user test traffic. |
| `bash run.sh first-setup-openbao` | Initialize OpenBao and supported secrets. |

`switch-profile` and tier profiles are retired. `update-omnirouter` and
`sync-omnirouter` are compatibility command names for OmniRoute maintenance.

## Safe clean-deploy sequence

```bash
cd /opt/assistant
bash run.sh backup
bash run.sh verify
bash run.sh workers
bash run.sh destroy
bash run.sh up
bash run.sh ps
```

`destroy` is intentionally not a data wipe. A true empty-data disaster-recovery
exercise is a separate destructive procedure and requires an independently
verified backup, exact project-volume targets, and explicit authorization.

After `up`, verify OmniRoute/config and Zalo ownership before sending any test
traffic. First-setup is setup-only; tests follow [test/RULES.md](../test/RULES.md).

## Typical worker set

```bash
bash run.sh install schedule media security notify message monitor
bash run.sh workers
bash run.sh check-media
bash run.sh check-security
```

See [00-workers.md](./00-workers.md), [02-commands.md](./02-commands.md), and
[config/DEFAULTS.md](./config/DEFAULTS.md).
