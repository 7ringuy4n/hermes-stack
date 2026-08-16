# Profiles

`ASSISTANT_PROFILE` selects compose overlays under [`docker/`](../docker/README.md).
Runtime data stays on the host (`ASSISTANT_DATA_DIR`, default `/data/assistant`).

| Profile | Intent |
|---------|--------|
| **low** | Must-have: Hermes, 9Router, memory, redis, core ingest/embedding |
| **medium** | Low + web search, OCR, jobs, ComfyUI CPU, daily compact; Hermes×2 default; edge on by default |
| **high** | Medium + OpenBao, authz, admin-api, SIEM; optional **monitor** (Grafana/Loki/Prometheus/Alloy); optional Zalo; Hermes×2 default |

```bash
export ASSISTANT_PROFILE=low    # or medium | high
bash run.sh up
```

High without observability containers:

```bash
export ASSISTANT_PROFILE=high
export ENABLE_GRAFANA=0 ENABLE_LOKI=0 ENABLE_PROMETHEUS=0 ENABLE_ALLOY=0
bash run.sh up
```

When `HERMES_REPLICAS>1`, host ports `:29119` / `:28642` are not published — tunnel Traefik (`8080`) and/or API Gateway (`8088`) instead.

## Hardware

See [HARDWARE.md](./HARDWARE.md) for **tested lab specs** (High on 4 vCPU / 16 GiB / ~200 GB) and **recommended minimums** per profile.

## Related

- [02-components-and-commands.md](./02-components-and-commands.md) — what each profile starts and which `run.sh` checks apply  
- [docker/README.md](../docker/README.md) — compose files and component profiles  
- [architect/backup-restore/README.md](../architect/backup-restore/README.md) — backup / restore / verify  
