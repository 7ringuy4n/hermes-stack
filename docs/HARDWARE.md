# Hardware requirements

English guide for sizing a self-hosted **assistant** (Hermes) stack. Compose files live under [`docker/`](../docker/README.md). Runtime data defaults to `/data/assistant`.

**SoT for add-on cost.** Other docs that mention hardware point here. Enabling optional **workers** adds RAM, disk, and CPU on top of the **core** base — exporters start only with the component they scrape.

## Tested lab (successful full-worker deploy + DR)

| Item | Value |
|------|-------|
| Date | 2026-08-16 |
| OS | Ubuntu **24.04.4 LTS** (Noble), kernel 6.8.x |
| CPU | **4 vCPU** (AMD EPYC 9354P slice) |
| RAM | **16 GiB** (no swap) |
| Disk | **~200 GB** SSD (`/` and data on same volume) |
| Workers | schedule + media + security + notify + message (Zalo); `HERMES_REPLICAS=2` |
| Monitor | Off (`ENABLE_GRAFANA=inactive`, `ENABLE_LOKI=inactive`, `ENABLE_PROMETHEUS=inactive`, `ENABLE_ALLOY=inactive`) |
| Channels | Zalo bridge logged in; Traefik + API Gateway on |
| Workloads verified | Stack up; image smoke (vendor); gateway concurrency 20× `/health` → 200; SearXNG weather; **backup → verify → restore** round-trip (see [architect/backup-restore/README.md](../architect/backup-restore/README.md)) |

This size is a comfortable **core + media + security + message without Grafana/Loki/Prometheus** reference. Idle RAM on that run was roughly **~3 GiB** used with large cache; peak under ComfyUI CPU + dual Hermes is higher.

## Recommended minimums (worker base)

Sizes below assume Docker + Compose on a clean Ubuntu 24.04 host, models routed via **OmniRouter** (default; no large local LLM weights on disk), and data on a single SSD. **Add** the extras in [Additional usage when you enable features](#additional-usage-when-you-enable-features) if those flags/workers are on.

| Setup | Min (boot / light use) | Comfortable (daily use) | Notes |
|---------|------------------------|-------------------------|-------|
| **Core only** | **2 vCPU · 4 GiB · 40 GB** | 2 vCPU · 8 GiB · 80 GB | Hermes×1, memory, Valkey, ingest/embed, model-router + Omni |
| **Core + media** | **2 vCPU · 8 GiB · 80 GB** | **4 vCPU · 16 GiB · 120 GB** | + SearXNG, OCR, jobs, ComfyUI CPU |
| **Core + media + security + message** (monitor **off**) | **4 vCPU · 8 GiB · 100 GB** | **4 vCPU · 16 GiB · 200 GB** | + OpenBao, authz, SIEM, zalo-api; Hermes×2 typical |
| **Above + monitor + all optionals** | **6 vCPU · 16 GiB · 140 GB** | **8 vCPU · 32 GiB · 250 GB** | Base set + **~5 GiB RAM · ~40 GB disk · ~2 vCPU** |

Install workers with `bash run.sh install …` — see [00-workers.md](./00-workers.md).

## Additional usage when you enable features

Approximate **idle/typical** extras on top of a media+security+message host without monitor (~3 GiB RAM idle). Disk is working set (images + TSDB + logs), not the whole host SSD. CPU is extra vCPU to leave for that combo (not a hard cgroup limit).

| Enable | Starts together (paired) | Extra RAM | Extra disk | Extra CPU |
|--------|--------------------------|-----------|------------|-----------|
| **Monitor** (`install monitor` → Grafana + Prometheus) | Prometheus + exporters (`node-exporter`, `stack-exporter`; `omni-exporter` only if OmniRoute on) | **~1.5 GiB** | **~10 GB** (Prom TSDB 15d + Grafana) | **~0.5 vCPU** |
| **Prometheus** only | Same exporters (no Grafana UI) | **~0.8 GiB** | **~8 GB** (TSDB) | **~0.3 vCPU** |
| **Loki + Alloy** (bundled in monitor) | Loki and Alloy always together | **~1.5 GiB** | **~20 GB** (log chunks; grows with traffic) | **~0.5 vCPU** |
| **OmniRouter** (core default) | **`omni-exporter`** when Prometheus/Grafana is also on | **~0.4 GiB** | **~1 GB** | **~0.2 vCPU** |
| **Notify** (`install notify`) | `alert-watch` | **~0.2 GiB** | — | **~0.1 vCPU** |
| **Antivirus** (`install antivirus`) | ClamAV + av-gateway | **~0.8 GiB** | **~2 GB** (defs) | **~0.3 vCPU** (scan spikes higher) |
| **Message / Zalo** (`install message`) | zalo-api + host bridge | **~0.3 GiB** | **~1 GB** | **~0.1 vCPU** |
| **All optional features** | Monitor + paired exporters + Notify + AV + Zalo + … | **~5 GiB** | **~40 GB** | **~1–2 vCPU** (plan **+2 vCPU**) |

**Examples**

- Grafana + Prometheus (metrics + Hardware + router/stack), Loki off: **~1.5 GiB RAM · ~10 GB disk · ~0.5 vCPU**.
- Loki + Alloy (logs) without Grafana: **~1.5 GiB RAM · ~20 GB disk · ~0.5 vCPU**.
- Grafana + Prometheus **and** Loki + Alloy: **~3 GiB RAM · ~30 GB disk · ~1 vCPU**.
- Enable **everything** optional: **~5 GiB RAM · ~40 GB disk · ~2 vCPU** → expect ~8 GiB RAM used and ~6 vCPU busy-capable on the 16 GiB / 4 vCPU lab host (that host is RAM-comfortable, CPU-tight with all optionals — prefer **8 vCPU**).

Do not enable Grafana without Prometheus: `run.sh` starts Prometheus (and Hardware/`node-exporter`) together with Grafana. Do not enable Loki without Alloy: they start together. Prefer `bash run.sh install monitor` so the bundle stays consistent.

### Exporter ↔ component pairs

| Component | Exporter | When it starts |
|-----------|----------|----------------|
| OmniRoute | `omni-exporter` | OmniRoute **and** Prometheus/Grafana |
| OmniRouter | `omni-exporter` | OmniRouter **and** Prometheus/Grafana |
| Host hardware (Grafana CPU/RAM panels) | `node-exporter` | Prometheus or Grafana |
| Stack health (`assistant_service_up`) | `stack-exporter` | Prometheus or Grafana |
| Container logs | Alloy → Loki | Loki or Alloy |

## Guidance

- Prefer **SSD**; keep at least **20% free** on the data volume for backups and Docker layers.
- **Hermes replicas > 1** need more RAM/CPU; host ports `:29119` / `:28642` are only published when `HERMES_REPLICAS=1` — use Traefik (`:8080`) / API Gateway (`:8088`) tunnels instead.
- **ComfyUI CPU** image gen is slow and memory-hungry; GPU overlay is optional (`COMFYUI_HAS_GPU=1`).
- **Swap:** optional on small VPS; 2–4 GiB swap helps media on 8 GiB hosts, but SSD + enough RAM is better.
- **Backups** grow under `/data/assistant/backups` (retention `BACKUP_RETENTION_DAYS`, default 14). Size disk for at least one full stamp plus working set.

## Flags that change footprint

| Flag / component | Extra RAM | Extra disk | Extra CPU |
|------------------|-----------|------------|-----------|
| `ENABLE_GRAFANA` (pairs Prometheus + node/stack exporters) | ~1.5 GiB | ~10 GB | ~0.5 vCPU |
| `ENABLE_PROMETHEUS` (exporters, no Grafana UI) | ~0.8 GiB | ~8 GB | ~0.3 vCPU |
| `ENABLE_LOKI` / `ENABLE_ALLOY` (always together) | ~1.5 GiB | ~20 GB | ~0.5 vCPU |
| `ENABLE_OMNIROUTER` (+ `omni-exporter` when metrics on) | ~0.4 GiB | ~1 GB | ~0.2 vCPU |
| `HERMES_REPLICAS=2` | second Hermes process | — | ~0.5–1 vCPU |
| `ENABLE_ZALO=active` | ~0.3 GiB | ~1 GB | ~0.1 vCPU |
| `ENABLE_NOTIFY=active` | ~0.2 GiB | — | ~0.1 vCPU |
| `ENABLE_ANTIVIRUS=active` | ~0.8 GiB | ~2 GB | ~0.3 vCPU |
| `ENABLE_CLOUDDRIVE=active` | sync bursts | mirror size | I/O bound |
| `COMFYUI_HAS_GPU=1` | VRAM + RAM | model weights | GPU |
| **All optional features** | **~5 GiB** | **~40 GB** | **~2 vCPU** |

## Related

- [00-workers.md](./00-workers.md)
- [docker/README.md](../docker/README.md)
- [architect/monitor/README.md](../architect/monitor/README.md)
- Grafana scrape pairing: [test/cases/20-grafana-component-integration.md](../test/cases/20-grafana-component-integration.md)
- Router defaults: [test/cases/21-defaults-routers-connected.md](../test/cases/21-defaults-routers-connected.md)
- [architect/backup-restore/README.md](../architect/backup-restore/README.md)
- Root [README.md](../README.md)
