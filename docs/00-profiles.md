# Profiles

`ASSISTANT_PROFILE` selects compose overlays. Container names are plain
(`hermes`, `memory`, `redis`, …) — no legacy lab prefixes.

| Profile | Intent |
|---------|--------|
| **low** | Must-have: Hermes, 9Router, memory, redis, core ingest/embedding |
| **medium** | Low + web search, OCR, jobs, ComfyUI CPU, daily compact |
| **high** | Medium + OpenBao, Grafana stack, authz, admin-api, SIEM; optional Zalo |

```bash
export ASSISTANT_PROFILE=low    # or medium | high
bash run.sh up
```

See [02-components-and-commands.md](./02-components-and-commands.md) for what each
profile starts and which `run.sh` checks apply.
