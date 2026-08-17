# Profiles

`ASSISTANT_PROFILE` selects compose overlays under [`docker/`](../docker/README.md).
Runtime data stays on the host (`ASSISTANT_DATA_DIR`, default `/data/assistant`).

| Profile | Intent |
|---------|--------|
| **low** | Must-have + Traefik/Gateway by default; Hermes×1; optionals allowed if `ENABLE_*=1` |
| **medium** | Low + OCR, jobs, SearXNG, Comfy CPU; Hermes×1; edge on |
| **high** | Medium + OpenBao, authz, SIEM, …; Hermes×2 on **one node**; monitor optional |

```bash
export ASSISTANT_PROFILE=low    # or medium | high
bash run.sh up
```

## Traefik modes (v0.5.0)

| Mode | Behavior |
|------|----------|
| `TRAEFIK_MODE=public` (default) | Prefer ACME when email+domain set; otherwise **fail-soft to local** |
| `TRAEFIK_MODE=local` | HTTP on `127.0.0.1:8080` only |

High without observability:

```bash
export ASSISTANT_PROFILE=high
export ENABLE_GRAFANA=0 ENABLE_LOKI=0 ENABLE_PROMETHEUS=0 ENABLE_ALLOY=0
bash run.sh up
```

When `HERMES_REPLICAS>1`, host ports `:29119` / `:28642` are not published — use Traefik (`8080`) and/or API Gateway (`8088`).

## Related

- [06-model-routing.md](./06-model-routing.md) — 9router / OmniRouter / Model Router  
- [MULTI_NODE.md](./MULTI_NODE.md) — Hermes×2 vs true HA  
- [HARDWARE.md](./HARDWARE.md)  
