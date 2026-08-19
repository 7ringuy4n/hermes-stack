# Model Router (v0.5.0)

## System architecture

| | |
|--|--|
| **Sits between** | Hermes ↔ 9router / OmniRouter / fallback pool |
| **Owns** | Hybrid task class + provider health + clear `no_model_available` |
| **Does not own** | Skill definitions (Hermes) or tool HTTP (dispatcher) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Hermes</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>model-router</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">9router · Omni · fallback</td>
  </tr>
</table>

## Purpose

OpenAI-compatible proxy between Hermes and LLM providers. Classifies **task_hint** (not security). `NORMAL` is the fast path (no extra classifier LLM). `SECRET` is never a task type.

## Classification (hybrid)

1. Client header `X-Task-Type`
2. Request `metadata.task_hint` / `metadata.task_type` (Hermes)
3. Default → **normal** (fast path)
4. `POST /v1/classify` — LLM returns `task_hint`, `instructions`, `cadence`, `cron_expr`

Hints: `normal` · `schedule` · `coding` · `tool` · `search` · `file` · `unknown`  
Aliases: `general`/`chat` → `normal`, `code` → `coding`. Values `secret`/`blocked` are ignored (Secret Probe owns security).

Prompt file: `config/classify.json` (admin-editable). Application code validates the JSON protocol only.

## Providers

| Task | Preferred | Then |
|------|-----------|------|
| coding | 9router (if healthy) | OmniRouter if only that exists → OpenAI fallback (if keyed) → Ollama (if configured) |
| normal / schedule / tool / search / file / unknown | OmniRouter (if `ENABLE_OMNIROUTER=1` and healthy) | 9router → fallbacks |

Missing API keys skip that provider. If nothing works → JSON error `no_model_available` (message in `messages/en.json`).

## Enable

- `ENABLE_MODEL_ROUTER=1` (default)
- `ENABLE_OMNIROUTER=0|1` (optional separate OmniRouter image)
- Hermes: `HERMES_OPENAI_BASE_URL=http://model-router:8096/v1`

## Timeouts

`MODEL_ROUTER_TIMEOUT_S` (default 90). Health probes cached `MODEL_ROUTER_HEALTH_TTL_S` (default 15).

## Multi-node

Hermes×2 on one node is supported. Multi-node Hermes is docs-only in v0.5.0; Valkey/Postgres/Qdrant remain SPOFs.
