# 01 — Request and data workflow

**As of:** 2026-09-05

## Request path

```text
Hermes console / Zalo bridge → proxy → Traefik
              │
              ▼
     per-conversation queue
              │
              ▼
        classify contract
              │
              ▼
 model-router → OmniRoute combo
              │
   ┌──────────┼──────────────┬─────────────┬─────────────┐
   ▼          ▼              ▼             ▼             ▼
hermes    image-gen      image-edit    vision-ocr    web-search
 chat      still image    quoted/file    natural       search
 combo      creation       editing       analysis       combo
   └──────────┴──────────────┴─────────────┴─────────────┘
              │
              ▼
       one final reply/file
```

The classify prompt is assembled from
`hermes/main/skills/classify/classify.json` and its English, general-purpose
`parts/`. Application code must not duplicate that prompt or classify user
prose with regex/keyword rules.

For Zalo, the host bridge owns the account session. The proxy exposes it only
on the internal network, Traefik provides the stable routed endpoint, and a
renewable Valkey lease elects exactly one Hermes SSE consumer. Standby replicas
keep the adapter loaded and acquire after lease expiry without a full replica
restart. Inbound events then enter a Valkey-backed per-conversation queue;
different conversations may run concurrently while the same conversation
remains ordered. A reply-quote may provide the source media for `image-edit`;
the adapter stages that attachment before invoking the skill.

## State ownership

| State | Owner | Recovery property |
|---|---|---|
| Recent conversation, locks, inbound queues | Valkey | Ephemeral; TTL/queue data may be rebuilt. |
| Durable facts, sessions, workflows, schedules, Zalo metadata | PostgreSQL | Backed up before lifecycle mutations. |
| Knowledge and conversational vectors | Qdrant | Durable volume; knowledge can be re-ingested. |
| Source documents and generated media | `/data/assistant` | Backed up separately from containers. |
| Provider credentials | OpenBao | Never written to reports; exported by the backup component. |
| Providers, accounts, combos, routing strategy | OmniRoute data volume/export | Preserved on update; operator combo membership is not rewritten. |
| Hermes runtime home | one directory per replica | Prevents shared SQLite/session mutation between replicas. |
| Zalo owner + inbound ordering | Valkey lease and per-thread queues | One SSE owner; failover after lease expiry; duplicate-safe ordered turns. |

Embedding is a service path, not an LLM chat fallback. Ingest and memory
optimization use the `embedding` combo. Web retrieval uses the `web-search`
combo. Image analysis uses `vision-ocr`; no PaddleOCR/Tesseract container is
part of the current architecture.

## Core and optional workers

Core services are PostgreSQL, Valkey, Qdrant, memory, session, workflow,
embedding, ingest, model-router, OmniRoute, omni-attribution, Hermes, Traefik,
and API Gateway.

| Worker | Adds |
|---|---|
| `schedule` | Schedule worker and timed delivery. |
| `media` | Dispatcher, jobs, jobs-worker, and SearXNG support. |
| `security` | OpenBao/security policy components. |
| `notify` | Notification and alert watcher. |
| `message` / `zalo` | Zalo proxy/API plus the host systemd bridge. |
| `monitor` | Prometheus, Grafana, Loki, and Alloy. |

There are no supported `video-gen` or `video-edit` skills/combos. Image edit
is supported only when the configured `image-edit` combo has a live capable
member.

## Reliability boundaries

- `HERMES_REPLICAS=2` gives process redundancy; it does not make PostgreSQL,
  Valkey, Qdrant, OmniRoute, or the single Zalo account owner highly available.
- Stack and alert watchers restart only unhealthy owned components. Repeated
  restarts require log/root-cause investigation; they are not a normal retry
  mechanism.
- Model queue saturation, quota exhaustion, and provider latency are recorded
  separately from service hangs. Long image operations use their own bounded
  deadline.
- Scheduled and asynchronous jobs acknowledge once, then deliver one final
  result. Setup commands do not inject test traffic.

See [03-architecture.md](./03-architecture.md),
[06-model-routing.md](./06-model-routing.md), and
[test/RULES.md](../test/RULES.md).
