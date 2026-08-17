# Model Router (v0.5.0)

## Purpose

OpenAI-compatible proxy between Hermes and LLM providers. Separates **coding** vs **general** tasks and applies fallbacks without hanging Hermes.

## Classification (hybrid)

1. Client header `X-Task-Type: coding|general`
2. Request `metadata.task_hint` / `metadata.task_type` (Hermes)
3. Heuristic patterns in `config/heuristic.json` (admin-editable)
4. Unknown → **general**

## Providers

| Task | Preferred | Then |
|------|-----------|------|
| coding | 9router (if healthy) | OmniRouter if only that exists → OpenAI fallback (if keyed) → Ollama (if configured) |
| general | OmniRouter (if `ENABLE_OMNIROUTER=1` and healthy) | 9router → fallbacks |

Missing API keys skip that provider. If nothing works → JSON error `no_model_available` (message in `messages/en.json`).

## Enable

- `ENABLE_MODEL_ROUTER=1` (default)
- `ENABLE_OMNIROUTER=0|1` (optional separate OmniRouter image)
- Hermes: `HERMES_OPENAI_BASE_URL=http://model-router:8096/v1`

## Timeouts

`MODEL_ROUTER_TIMEOUT_S` (default 90). Health probes cached `MODEL_ROUTER_HEALTH_TTL_S` (default 15).

## Multi-node

Hermes×2 on one node is supported. Multi-node Hermes is docs-only in v0.5.0; Valkey/Postgres/Qdrant remain SPOFs.
