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
| `ENABLE_OMNIROUTER` | 0 | Start OmniRouter (compose profile `omnirouter`) |
| `OMNIROUTER_IMAGE` | lab fallback 9router image | **Set your OmniRouter image** for production |
| `HERMES_REPLICAS` | 1 (High=2) | One-node scale only; multi-node = docs |

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
