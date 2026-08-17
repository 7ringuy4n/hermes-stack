# Hardware requirements

English guide for sizing a self-hosted **assistant** (Hermes) stack. Compose files live under [`docker/`](../docker/README.md). Runtime data defaults to `/data/assistant`.

## Tested lab (successful High deploy + DR)

| Item | Value |
|------|-------|
| Date | 2026-08-16 |
| OS | Ubuntu **24.04.4 LTS** (Noble), kernel 6.8.x |
| CPU | **4 vCPU** (AMD EPYC 9354P slice) |
| RAM | **16 GiB** (no swap) |
| Disk | **~200 GB** SSD (`/` and data on same volume) |
| Profile | **High**, `HERMES_REPLICAS=2` |
| Monitor | Off (`ENABLE_GRAFANA=0`, `ENABLE_LOKI=0`, `ENABLE_PROMETHEUS=0`, `ENABLE_ALLOY=0`) |
| Channels | Zalo bridge logged in; Traefik + API Gateway on |
| Workloads verified | Stack up; image smoke (vendor); gateway concurrency 20× `/health` → 200; SearXNG weather; **backup → verify → restore** round-trip (see [architect/backup-restore/README.md](../architect/backup-restore/README.md)) |

This size is a comfortable **High without Grafana/Loki/Prometheus** reference. Idle RAM on that run was roughly ~3 GiB used with large cache; peak under ComfyUI CPU + dual Hermes is higher.

## Recommended minimums

Sizes below assume Docker + Compose on a clean Ubuntu 24.04 host, models routed via **9Router** (no large local LLM weights on disk), and data on a single SSD.

| Profile | Min (boot / light use) | Comfortable (daily use) | Notes |
|---------|------------------------|-------------------------|-------|
| **Low** | **2 vCPU · 4 GiB · 40 GB** | 2 vCPU · 8 GiB · 80 GB | Hermes×1, memory, Valkey, ingest/embed, 9Router |
| **Medium** | **2 vCPU · 8 GiB · 80 GB** | **4 vCPU · 16 GiB · 120 GB** | + SearXNG, OCR, jobs, ComfyUI CPU |
| **High** (monitor **off**) | **4 vCPU · 8 GiB · 100 GB** | **4 vCPU · 16 GiB · 200 GB** | + OpenBao, authz, SIEM, zalo-api (with Zalo); Hermes×2 default |
| **High** (monitor **on**) | **4 vCPU · 16 GiB · 150 GB** | **8 vCPU · 32 GiB · 250 GB** | + Grafana / Loki / Prometheus / Alloy |

### Guidance

- Prefer **SSD**; keep at least **20% free** on the data volume for backups and Docker layers.
- **Hermes replicas > 1** need more RAM/CPU; host ports `:29119` / `:28642` are only published when `HERMES_REPLICAS=1` — use Traefik (`:8080`) / API Gateway (`:8088`) tunnels instead.
- **ComfyUI CPU** image gen is slow and memory-hungry; GPU overlay is optional (`COMFYUI_HAS_GPU=1`).
- **Swap:** optional on small VPS; 2–4 GiB swap helps Medium on 8 GiB hosts, but SSD + enough RAM is better.
- **Backups** grow under `/data/assistant/backups` (retention `BACKUP_RETENTION_DAYS`, default 14). Size disk for at least one full stamp plus working set.

## Profile flags that change footprint

| Flag / component | Effect |
|------------------|--------|
| `ENABLE_GRAFANA` / `LOKI` / `PROMETHEUS` / `ALLOY` | Large disk + RAM for metrics/logs (High monitor profile) |
| `HERMES_REPLICAS=2` | Two Hermes gateways (High/Medium default) |
| `ENABLE_ZALO=1` | Extra Node bridge container + SSE |
| `ENABLE_CLOUDDRIVE=1` | Mirror / sync storage |
| `COMFYUI_HAS_GPU=1` | GPU image path (needs NVIDIA toolkit) |

## Related

- [00-profiles.md](./00-profiles.md)
- [docker/README.md](../docker/README.md)
- [architect/backup-restore/README.md](../architect/backup-restore/README.md)
- Root [README.md](../README.md)
