# Multi-node notes (v0.5.0)

## What is supported now

| Component | Support |
|-----------|---------|
| Hermes | **×2 on one node** (optional `HERMES_REPLICAS=2`). Not true HA. |
| Jobs workers | Scale workers; shared Valkey RQ queue |
| Zalo SSE | **Exactly one** SSE owner via `zalo_owner` lock — never 2 clients |
| Valkey / Postgres / Qdrant / Traefik | **Single-node SPOFs** — HA later |

## Single points of failure (be explicit)

| Store / hop | Role | If it dies |
|-------------|------|------------|
| **Valkey** | Short-term session, gateway rate-limit, RQ jobs, Zalo owner helpers | Sessions drop; queues pause; RL/gateway may 503 |
| **Postgres** | Durable facts + authz ACL | Memory/authz unhealthy until reconnect |
| **Qdrant** | Knowledge chunks (rebuildable) | Cite/search empty until restore/re-ingest |
| **Traefik / Gateway** | HTTP edge | Dashboard/API via edge down; Zalo path can still work on host bridge |
| **Zalo bridge (host)** | Upstream plugin | Needs manual QR if `sessionDead` — watches cannot invent a login |
| **zalo-proxy** | Docker hop to Hermes | Auto-started by `zalo-watch` when exited |

Self-heal covers **container exit / SSE miss** (`stack-watch`, `zalo-watch`). It does **not** replicate Valkey/Postgres/Qdrant.

## Multi-node (docs / runbook only)

When you place Hermes on two VMs later:

1. Point both at the **same** Valkey / Postgres / Qdrant hosts.
2. Share `HERMES_SHARED_DATA` (or NFS) so `zalo_owner` remains a cluster singleton.
3. Run `zalo-proxy` / bridge on **one** node only.
4. Keep Model Router + 9router / OmniRouter reachable from both Hermes instances.

Do **not** call this HA until stores are replicated.

## Related

- [00-workers.md](./00-workers.md)
- [00-profiles.md](./00-profiles.md) (legacy)
- [03-architecture.md](./03-architecture.md)
- [06-model-routing.md](./06-model-routing.md)
- [HARDWARE.md](./HARDWARE.md) — extra RAM/disk/CPU when Grafana/Prometheus/Loki/OmniRouter are on
