# Model routing & OmniRouter (v0.5.0)

## Goal

Keep Hermes answering when a preferred LLM path fails. **task_hint** selects the pipeline; **Secret Probe** decides whether processing is allowed.

```text
Hermes → INPUT Secret Probe → task_hint → model-router
  NORMAL  → Direct LLM (9router / Omni)
  CODING  → 9router
  SCHEDULE → Schedule Manager (workflow) — not model-router state
  TOOL / SEARCH / FILE → dedicated pipelines
  UNKNOWN → LLM with context
         → OUTPUT Secret Probe → user
```

## Classification (hybrid)

1. `X-Task-Type` (`normal|schedule|coding|tool|search|file|unknown`; aliases `general`→`normal`)
2. Hermes `metadata.task_hint` / `task_type`
3. Default → **normal** (fast path). Never `SECRET` as a task type.
4. Multi-task / schedule intercept: `POST /v1/classify` (LLM JSON). Prompt SoT: Hermes skill [`hermes/main/skills/classify/classify.json`](../hermes/main/skills/classify/classify.json) (mounted into router-worker). Related SoTs: [`outbound`](../hermes/main/skills/outbound/outbound.json), [`web-search-combo`](../hermes/main/skills/web-search/web-search-combo.json). Bake fallbacks under `architect/models/model-router/config/` via `scripts/main/sync-model-router-skills.sh`.
   Fast Dispatcher fields on the same JSON: `execution_class` (`interactive`|`async`|`schedule`), `task_type`, `response_mode` (`ack_then_deliver`|`confirm`; never `direct`).
   All user-facing answers route through model-router workers (Hermes chat combo, web_search, media_file, schedule). Classify only structures work — it never replies to the user.
   Zalo inbound always classifies purpose through this skill contract before routing.

Do not classify user prose with split/join/regex/keyword lists in application code.

## Flags

| Flag | Default | Meaning |
|------|---------|---------|
| `ENABLE_MODEL_ROUTER` | 1 | Run model-router; Hermes `OPENAI_BASE_URL` points here |
| `ENABLE_OMNIROUTER` | 1 | Start OmniRouter (compose profile `omnirouter`). This is the default general path. When Grafana/Prometheus is on, **`omni-exporter` starts with it**. |
| `OMNIROUTER_IMAGE` | `diegosouzapw/omniroute:latest` | Dedicated OmniRoute image (not 9router) |
| `ENABLE_9ROUTER` | 0 | Optional coding / fallback path. Enable explicitly when needed. |
| `HERMES_REPLICAS` | 1 | One-node scale only; multi-node = docs |

Hermes must always reach **model-router**. **OmniRouter** is the default general path. **9Router** is optional and should be enabled only when the coding/fallback component is wanted. Tests: [test/cases/21-defaults-routers-connected.md](../test/cases/21-defaults-routers-connected.md). Grafana pairing: [test/cases/20-grafana-component-integration.md](../test/cases/20-grafana-component-integration.md).

### Combo aliases (`hermes` chat, `classifier` classify)

There is no standalone vendor model id `hermes` or `classifier` — both are **combo aliases**.

| Who | What to set |
|-----|-------------|
| Hermes Agent `model.default` | chat combo (`OMNIROUTER_DEFAULT_COMBO`, default `hermes`) |
| `MODEL_ROUTER_OUTBOUND_MODEL` | same chat combo |
| `MODEL_ROUTER_CLASSIFY_MODEL` / `OMNIROUTER_CLASSIFY_COMBO` | classify combo (default `classifier`) |
| OmniRouter Combos UI | Chat members for `hermes` are operator-managed; **`classifier` is filled with all OpenCode Free `oc/*` models by `first-setup-omnirouter`** |

`first-setup-omnirouter` ensures:
- chat combo **name** `hermes` exists (does not overwrite chat members)
- classify combo **`classifier`** exists and is updated with the current OpenCode Free catalog

If Omni logs show **PROVIDER=HERMES** and **503**, the chat combo was not resolved. Add working members in the Combos UI (and connect providers), then retry.

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
