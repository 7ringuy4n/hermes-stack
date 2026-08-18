# Hardware requirements

English guide for sizing a self-hosted **assistant** (Hermes) stack. Compose files live under [`docker/`](../docker/README.md). Runtime data defaults to `/data/assistant`.

**SoT for add-on cost.** Other docs that mention hardware point here. Enabling optional components **adds RAM, disk, and CPU** on top of the profile base — exporters start only with the component they scrape.

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

This size is a comfortable **High without Grafana/Loki/Prometheus** reference. Idle RAM on that run was roughly **~3 GiB** used with large cache; peak under ComfyUI CPU + dual Hermes is higher.

## Recommended minimums (profile base)

Sizes below assume Docker + Compose on a clean Ubuntu 24.04 host, models routed via **9Router** (no large local LLM weights on disk), and data on a single SSD. **Add** the extras in [Additional usage when you enable features](#additional-usage-when-you-enable-features) if those flags are on.

| Profile | Min (boot / light use) | Comfortable (daily use) | Notes |
|---------|------------------------|-------------------------|-------|
| **Low** | **2 vCPU · 4 GiB · 40 GB** | 2 vCPU · 8 GiB · 80 GB | Hermes×1, memory, Valkey, ingest/embed, 9Router |
| **Medium** | **2 vCPU · 8 GiB · 80 GB** | **4 vCPU · 16 GiB · 120 GB** | + SearXNG, OCR, jobs, ComfyUI CPU |
| **High** (monitor **off**) | **4 vCPU · 8 GiB · 100 GB** | **4 vCPU · 16 GiB · 200 GB** | + OpenBao, authz, SIEM, zalo-api (with Zalo); Hermes×2 default |
| **High** + **all optional features** | **6 vCPU · 16 GiB · 140 GB** | **8 vCPU · 32 GiB · 250 GB** | Base High + **~5 GiB RAM · ~40 GB disk · ~2 vCPU** |

## Additional usage when you enable features

Approximate **idle/typical** extras on top of the profile base (~3 GiB RAM idle High without monitor). Disk is working set (images + TSDB + logs), not the whole host SSD. CPU is extra vCPU to leave for that combo (not a hard cgroup limit).

| Enable | Starts together (paired) | Extra RAM | Extra disk | Extra CPU |
|--------|--------------------------|-----------|------------|-----------|
| **Grafana + Prometheus** (`ENABLE_GRAFANA=1`) | Prometheus + `nine-exporter` + `node-exporter` (Hardware panels) + `stack-exporter` | **~1.5 GiB** | **~10 GB** (Prom TSDB 15d + Grafana) | **~0.5 vCPU** |
| **Prometheus** only (`ENABLE_PROMETHEUS=1`) | Same exporters (no Grafana UI) | **~0.8 GiB** | **~8 GB** (TSDB) | **~0.3 vCPU** |
| **Loki + Alloy** (`ENABLE_LOKI=1` or `ENABLE_ALLOY=1`) | Loki and Alloy always together | **~1.5 GiB** | **~20 GB** (log chunks; grows with traffic) | **~0.5 vCPU** |
| **OmniRouter** (`ENABLE_OMNIROUTER=1`) | **`omni-exporter`** when Prometheus/Grafana is also on | **~0.4 GiB** | **~1 GB** | **~0.2 vCPU** |
| **Notify** (`ENABLE_NOTIFY=1`) | `alert-watch` | **~0.2 GiB** | — | **~0.1 vCPU** |
| **Antivirus** (`ENABLE_ANTIVIRUS=1`) | ClamAV + av-gateway | **~0.8 GiB** | **~2 GB** (defs) | **~0.3 vCPU** (scan spikes higher) |
| **Zalo** (`ENABLE_ZALO=1`) | zalo-api + host bridge | **~0.3 GiB** | **~1 GB** | **~0.1 vCPU** |
| **All optional features** | Grafana+Prometheus **and** Loki+Alloy + paired exporters + OmniRouter + Notify + AV + Zalo + … | **~5 GiB** | **~40 GB** | **~1–2 vCPU** (plan **+2 vCPU**) |

**Examples**

- Grafana + Prometheus (metrics + Hardware + 9Router/stack), Loki off: **~1.5 GiB RAM · ~10 GB disk · ~0.5 vCPU**.
- Loki + Alloy (logs) without Grafana: **~1.5 GiB RAM · ~20 GB disk · ~0.5 vCPU**.
- Grafana + Prometheus **and** Loki + Alloy: **~3 GiB RAM · ~30 GB disk · ~1 vCPU**.
- Enable **everything** optional on High: **~5 GiB RAM · ~40 GB disk · ~2 vCPU** → expect ~8 GiB RAM used and ~6 vCPU busy-capable on the 16 GiB / 4 vCPU lab host (that host is RAM-comfortable, CPU-tight with all optionals — prefer **8 vCPU**).

Do not enable Grafana without Prometheus: `run.sh` starts Prometheus (and Hardware/`node-exporter`) together with Grafana. Do not enable Loki without Alloy: they start together.

### Exporter ↔ component pairs

| Component | Exporter | When it starts |
|-----------|----------|----------------|
| 9Router | `nine-exporter` | Prometheus or Grafana |
| OmniRouter | `omni-exporter` | OmniRouter **and** Prometheus/Grafana |
| Host hardware (Grafana CPU/RAM panels) | `node-exporter` | Prometheus or Grafana |
| Stack health (`assistant_service_up`) | `stack-exporter` | Prometheus or Grafana |
| Container logs | Alloy → Loki | Loki or Alloy |

## Guidance

- Prefer **SSD**; keep at least **20% free** on the data volume for backups and Docker layers.
- **Hermes replicas > 1** need more RAM/CPU; host ports `:29119` / `:28642` are only published when `HERMES_REPLICAS=1` — use Traefik (`:8080`) / API Gateway (`:8088`) tunnels instead.
- **ComfyUI CPU** image gen is slow and memory-hungry; GPU overlay is optional (`COMFYUI_HAS_GPU=1`).
- **Swap:** optional on small VPS; 2–4 GiB swap helps Medium on 8 GiB hosts, but SSD + enough RAM is better.
- **Backups** grow under `/data/assistant/backups` (retention `BACKUP_RETENTION_DAYS`, default 14). Size disk for at least one full stamp plus working set.

## Profile flags that change footprint

| Flag / component | Extra RAM | Extra disk | Extra CPU |
|------------------|-----------|------------|-----------|
| `ENABLE_GRAFANA` (pairs Prometheus + nine/node/stack exporters) | ~1.5 GiB | ~10 GB | ~0.5 vCPU |
| `ENABLE_PROMETHEUS` (exporters, no Grafana UI) | ~0.8 GiB | ~8 GB | ~0.3 vCPU |
| `ENABLE_LOKI` / `ENABLE_ALLOY` (always together) | ~1.5 GiB | ~20 GB | ~0.5 vCPU |
| `ENABLE_OMNIROUTER` (+ `omni-exporter` when metrics on) | ~0.4 GiB | ~1 GB | ~0.2 vCPU |
| `HERMES_REPLICAS=2` | second Hermes process | — | ~0.5–1 vCPU |
| `ENABLE_ZALO=1` | ~0.3 GiB | ~1 GB | ~0.1 vCPU |
| `ENABLE_NOTIFY=1` | ~0.2 GiB | — | ~0.1 vCPU |
| `ENABLE_ANTIVIRUS=1` | ~0.8 GiB | ~2 GB | ~0.3 vCPU |
| `ENABLE_CLOUDDRIVE=1` | sync bursts | mirror size | I/O bound |
| `COMFYUI_HAS_GPU=1` | VRAM + RAM | model weights | GPU |
| **All optional features** | **~5 GiB** | **~40 GB** | **~2 vCPU** |

## Related

- [00-profiles.md](./00-profiles.md)
- [docker/README.md](../docker/README.md)
- [architect/monitor/README.md](../architect/monitor/README.md)
- Grafana scrape pairing: [test/cases/20-grafana-component-integration.md](../test/cases/20-grafana-component-integration.md)
- Router defaults: [test/cases/21-defaults-routers-connected.md](../test/cases/21-defaults-routers-connected.md)
- [architect/backup-restore/README.md](../architect/backup-restore/README.md)
- Root [README.md](../README.md)
