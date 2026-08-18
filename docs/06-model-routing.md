# Model routing & OmniRouter (v0.5.0)

## Goal

Keep Hermes answering when a preferred LLM path fails, and split **coding** vs **other** tasks across routers.

```text
Hermes → model-router → 9router (coding) / OmniRouter (general) → fallback pool → clear error
```

## Classification (hybrid)

1. `X-Task-Type: coding|general`
2. Hermes `metadata.task_hint` / `task_type`
3. Heuristic file `architect/models/model-router/config/heuristic.json`
4. Unknown → **general**

## Flags

| Flag | Default | Meaning |
|------|---------|---------|
| `ENABLE_MODEL_ROUTER` | 1 | Run model-router; Hermes `OPENAI_BASE_URL` points here |
| `ENABLE_OMNIROUTER` | 1 (Low/Medium) / 0 (High) | Start OmniRouter (compose profile `omnirouter`). When Grafana/Prometheus is on, **`omni-exporter` starts with it**. |
| `OMNIROUTER_IMAGE` | `diegosouzapw/omniroute:latest` | Dedicated OmniRoute image (not 9router) |
| `HERMES_REPLICAS` | 1 (High=2) | One-node scale only; multi-node = docs |

Hermes must always reach **9Router**. OmniRouter is opt-in. Tests: [test/cases/21-defaults-routers-connected.md](../test/cases/21-defaults-routers-connected.md). Grafana pairing: [test/cases/20-grafana-component-integration.md](../test/cases/20-grafana-component-integration.md).

**Health:** `GET /v1/models` without an API key returns **401** while 9router is up (UI `/` is **307**). Stack-watch treats 200/401/307 as healthy — do not use `curl -f` on that URL or every heal tick will restart 9router.

## Memory (unchanged story)

| Store | Role |
|-------|------|
| Valkey | Short-term session (`conversation_active:*`) + locks + RQ |
| Postgres | Durable facts |
| Qdrant | Knowledge (rebuildable) |

Mem0 is removed.

## Related

- [architect/models/model-router/README.md](../architect/models/model-router/README.md)
- [architect/models/omni-router/README.md](../architect/models/omni-router/README.md)
- [docs/MULTI_NODE.md](./MULTI_NODE.md)
- [docs/HARDWARE.md](./HARDWARE.md) — extra usage (~0.4 GiB / ~1 GB / ~0.2 vCPU OmniRouter; Grafana+Prometheus ~1.5 GiB / ~10 GB / ~0.5 vCPU)
