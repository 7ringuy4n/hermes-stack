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

## Traefik modes (v0.5.3)

| Mode | Behavior |
|------|----------|
| `TRAEFIK_MODE=local` (**default**) | HTTP on `127.0.0.1:8080` only (VPN / SSH tunnel) |
| `TRAEFIK_MODE=public` | Prefer ACME when email+domain set; otherwise **fail-soft to local** |

High without observability:

```bash
export ASSISTANT_PROFILE=high
export ENABLE_GRAFANA=0 ENABLE_LOKI=0 ENABLE_PROMETHEUS=0 ENABLE_ALLOY=0
bash run.sh up
```

When `HERMES_REPLICAS>1`, host ports `:29119` / `:28642` are not published — use Traefik (`8080`) and/or API Gateway (`8088`).

## Change profile (upgrade / downgrade / add components)

All three profiles can move **up or down**. Runtime data stays on the host (`ASSISTANT_DATA_DIR`); named volumes are not wiped. Change **archives first** so you can restore the previous tier.

```bash
bash run.sh profile                              # current options
bash run.sh switch-profile medium                # archive + set ASSISTANT_PROFILE + up
bash run.sh switch-profile high --dry-run        # show plan only
bash run.sh add-components ENABLE_ZALO=1         # archive + set flags + up
bash run.sh restore "$(cat /data/assistant/backups/PRE_CHANGE)"   # undo last change
```

| Direction | What happens |
|-----------|----------------|
| Low → Medium / High | Extra compose overlays start; Medium+ defaults turn on OCR/jobs/SearXNG unless already set in `.env` |
| High → Medium / Low | `up --remove-orphans` drops High-only containers (OpenBao, authz, SIEM, …). Data volumes stay. High `ENABLE_*` left in `.env` are unused until you upgrade again |
| Add component | Any profile may set `ENABLE_*=1` (Zalo, Traefik, OCR on Low via medium overlay). High-only flags (OpenBao, authz, SIEM) need `ASSISTANT_PROFILE=high` |

`--no-up` writes `.env` and the stamp but does not recreate containers. Undo is always `bash run.sh restore <stamp>` (restores stores **and** `.env`).

## Related

- [06-model-routing.md](./06-model-routing.md) — 9router / OmniRouter / Model Router  
- [MULTI_NODE.md](./MULTI_NODE.md) — Hermes×2 vs true HA  
- [HARDWARE.md](./HARDWARE.md)  
