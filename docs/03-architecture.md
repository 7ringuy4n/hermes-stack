# 03 — System architecture

## Logical view

```text
Users
  ├─ Hermes console / HTTP → Traefik or API Gateway
  └─ Zalo → host bridge → zalo-proxy → Traefik
                                      │
                                      ▼
                         Valkey-elected Hermes owner
                                      │
                                      ▼
                           per-conversation queue
                         │
                         ▼
                 Hermes (1 or 2)
                         │
        ┌────────────────┼─────────────────┐
        ▼                ▼                 ▼
 memory/session     classify/skills   workflow/schedule
        │                │                 │
        ▼                ▼                 ▼
Postgres/Valkey   model-router       Postgres + worker
Qdrant                    │
                          ▼
                 OmniRoute priority combos
          hermes · classifier · web-search · image-gen
            vision-ocr · embedding · image-edit
```

## Deployment layers

| Layer | Ownership |
|---|---|
| `hermes/` | Agent configuration, skills, plugins, message contracts, replica runtime. |
| `architect/models/` | model-router, OmniRoute integration, attribution, dispatcher/jobs. |
| `architect/memory/` | Session, long-term memory, ingest, embedding clients. |
| `architect/social-app/` and `architect/zalo-api/` | Channel session, inbound/outbound API, queue ownership. |
| `architect/schedule-worker/` | Deterministic scheduled execution. |
| `architect/security/` | Secrets, policy, authorization, audit, optional antivirus. |
| `architect/monitor/` | Metrics, dashboards, logs, alerting and health observation. |
| `architect/backup-restore/` | Verified backup, restore, worker flags, migrations. |
| `docker/` | Core compose and optional overlays. |

## Capability paths

| Request | Path |
|---|---|
| Chat | Hermes → model-router → `hermes` combo |
| Classification | classify prompt → model-router → `classifier` combo → validated JSON |
| Web research | web-search skill/dispatcher → `web-search` combo |
| New still image | image-gen skill → `image-gen` combo |
| Image edit | attached/reply-quoted image → image-edit skill → `image-edit` combo |
| Image/document analysis | media staging → `vision-ocr` combo → natural analysis |
| Knowledge ingest | ingest → embedding service → `embedding` combo → Qdrant |
| Timed work | schedule skill → schedule-worker/Postgres → later queue injection |
| Office artifact | documents skill/file tooling → staged artifact → visual QA → outbound file |

There is no supported video generation/editing capability and no separate
PaddleOCR, Tesseract, ComfyUI, 9Router, or legacy OmniRouter service.

## Concurrency and availability

Hermes replicas share durable services but have isolated runtime homes. Every
replica loads the Zalo adapter against the Traefik bridge route; an expiring,
renewed Valkey lease permits exactly one active SSE consumer. If that replica
dies, a standby acquires the lease without restarting the replica set. The
inbound queue serializes work per conversation and permits unrelated
conversations to execute concurrently. Quote-reply correlation is carried as
message metadata and staged media, not inferred from global recent state.

Scaling Hermes from one to two replicas improves agent capacity only. On one
host, PostgreSQL, Valkey, Qdrant, OmniRoute, storage, and the Zalo owner remain
single points of failure. Multi-node deployment requires external/shared state
and explicit service HA; see [MULTI_NODE.md](./MULTI_NODE.md).

## Persistence and recovery

- PostgreSQL: durable facts, sessions, workflows, schedules, channel metadata.
- Valkey: short-lived context, locks, queues, rate limits.
- Qdrant: knowledge and conversational vectors.
- `/data/assistant`: documents, staged inbound media, generated artifacts.
- OpenBao: provider/service secrets.
- OmniRoute volume/export: accounts, providers, combo order/strategy/history.
- `/data/assistant/backups`: verified recovery stamps.

Lifecycle mutation is backup-gated. `destroy` removes project containers and
networks but retains volumes/data. See [02-commands.md](./02-commands.md).

## Operational invariants

- Prompt policy is file-based; no request-specific prompt hardcoding in code.
- Provider quota or queue saturation is not reported as a service crash.
- First setup configures only; live probes are run separately.
- Watchers restart only components that fail a component-specific health gate.
- Every live lab captures route/combo evidence, user-visible delivery, latency,
  logs, restart deltas, and semantic/visual self-evaluation.
