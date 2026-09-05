# Availability and scaling

## What is supported now

| Component | Support |
|-----------|---------|
| Hermes | Multiple replicas behind Traefik on one node; Zalo owner fails over by Valkey lease. |
| Jobs workers | Scale workers; shared Valkey RQ queue |
| Zalo SSE | **Exactly one** active SSE owner via a renewable Valkey lease; standby replicas remain ready |
| Valkey / Postgres / Qdrant / Traefik / storage | **Single-node SPOFs** — full HA requires external replication. |

## Single points of failure (be explicit)

| Store / hop | Role | If it dies |
|-------------|------|------------|
| **Valkey** | Short-term session, gateway rate-limit, RQ jobs, Zalo owner helpers | Sessions drop; queues pause; RL/gateway may 503 |
| **Postgres** | Durable facts + authz ACL | Memory/authz unhealthy until reconnect |
| **Qdrant** | Knowledge chunks (rebuildable) | Cite/search empty until restore/re-ingest |
| **Traefik / Gateway** | HTTP edge and internal Zalo bridge route | New API and Zalo adapter connections fail until Traefik recovers |
| **Zalo bridge (host)** | Upstream plugin | Needs manual QR if `sessionDead` — watches cannot invent a login |
| **zalo-proxy** | Docker hop between bridge and Traefik | Auto-started by `zalo-watch` when exited |

Self-heal covers **container exit / SSE miss** (`stack-watch`, `zalo-watch`). It does **not** replicate Valkey/Postgres/Qdrant.

## Multi-node (docs / runbook only)

When you place Hermes on two VMs later:

1. Point both at the **same** Valkey / Postgres / Qdrant hosts.
2. Share Valkey and keep `ZALO_OWNER_LEASE_KEY` identical so Zalo ownership remains a cluster singleton.
3. Run `zalo-proxy` / bridge on **one** node only.
4. Keep Model Router + OmniRoute reachable from both Hermes instances.

Do **not** call this HA until stores are replicated.

## Scaling signals

Replica counts are operational starting points, not guaranteed capacity:

| Observed condition | Action |
|---|---|
| One or two concurrent interactive requests | Start with two Hermes replicas for process failover. |
| Sustained queue growth or high agent CPU | Measure, then add a Hermes replica within host limits. |
| Image/vision/embedding latency with idle Hermes CPU | Scale/fix provider or worker capacity, not Hermes. |
| Mostly idle replicas | Scale down after a measured window. |

Do not derive a fixed “requests per replica” rule from a small lab. Compare the
same workload at one and two replicas and report provider time separately from
local queue/agent time.

## Related

- [00-workers.md](./00-workers.md)
- [00-profiles.md](./00-profiles.md) (legacy)
- [03-architecture.md](./03-architecture.md)
- [06-model-routing.md](./06-model-routing.md)
- [HARDWARE.md](./HARDWARE.md) — extra RAM/disk/CPU when Grafana/Prometheus/Loki/OmniRoute are on
