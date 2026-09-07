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
Postgres/Valkey   router-worker       Postgres + worker
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
| `architect/models/` | router-worker, OmniRoute integration, attribution, dispatcher/jobs. |
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
| Chat | Hermes → router-worker → `hermes` combo |
| Classification | classify prompt → router-worker → `classifier` combo → validated JSON |
| Web research | web-search skill/dispatcher → `web-search` combo |
| New still image | image-gen skill → `image-gen` combo |
| Image edit | attached/reply-quoted image → image-edit skill → `image-edit` combo |
| Image/document analysis | media staging → `vision-ocr` combo → natural analysis |
| Knowledge ingest | ingest → embedding service → `embedding` combo → Qdrant |
| Durable notes | classify → notes host route → scoped PostgreSQL note/date indexes + audit |
| Timed work | schedule skill → schedule-worker/Postgres → later queue injection |
| Stop active work | classify control intent → thread-local active task cancellation → queue continues |
| Office artifact | documents skill/file tooling → staged artifact → visual QA → outbound file |

There is no supported video generation/editing capability and no separate
PaddleOCR, Tesseract, ComfyUI, 9Router, or legacy OmniRouter service.

## Concurrency and availability

Hermes replicas share durable services but have isolated runtime homes. HTTP
requests are active-active: Traefik resolves the Compose `hermes` service and
selects a healthy replica. Zalo ingestion is active-passive: every replica
loads the adapter against Traefik's internal bridge route, while an expiring,
renewed Valkey lease permits exactly one active SSE consumer. If that replica
dies, a standby acquires the lease without restarting the replica set.

The elected Zalo owner writes an event to a Valkey FIFO keyed by conversation,
claims that conversation's Valkey worker lock, dequeues it, and executes the
turn locally. Its adapter sends the result back through Traefik, `zalo-proxy`,
and the host bridge to the event's original DM or group. There is no callback
to a separately selected ingress replica. Another conversation may run at the
same time. If ownership changes, queued state remains in Valkey; the new owner
continues it when the conversation is kicked, while duplicate message IDs and
worker leases prevent concurrent handling. Work already executing in the lost
process is not migrated and may need retry. Quote-reply correlation is carried
as message metadata and staged media, not inferred from global recent state.

Before durable admission, an owner-local sequencer processes SSE events in
arrival order for each conversation. Cancellation can still bypass the work
queue after deterministic access/addressing checks, but a slow semantic check
cannot allow a later ordinary message to overtake an earlier one. Claimed agent
turns use per-conversation locks, not one owner-wide lock.

This is therefore a hybrid single-node availability design: active-active for
HTTP, active-passive for the Zalo event stream, and shared queues for background
workers. Scaling Hermes from one to two replicas improves capacity and process
failover only. On one
host, PostgreSQL, Valkey, Qdrant, OmniRoute, storage, and the Zalo owner remain
single points of failure. Multi-node deployment requires external/shared state
and explicit service HA; see [MULTI_NODE.md](./MULTI_NODE.md).

## Persistence and recovery

- PostgreSQL: durable facts, scoped notes/audit, sessions, workflows, schedules, channel metadata.
- Valkey: short-lived context, locks, queues, rate limits.
- Qdrant: knowledge and conversational vectors.
- `/data/assistant`: documents, staged inbound media, generated artifacts.
- OpenBao: provider/service secrets and durable operational retention values.
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
