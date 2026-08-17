# Multi-node notes (v0.5.0)

## What is supported now

| Component | Support |
|-----------|---------|
| Hermes | **×2 on one node** (High default). Not true HA. |
| Jobs workers | Scale workers; shared Valkey RQ queue |
| Zalo SSE | **Exactly one** SSE owner via `zalo_owner` lock — never 2 clients |
| Valkey / Postgres / Qdrant / Traefik | **Single-node SPOFs** — HA later |

## Multi-node (docs / runbook only)

When you place Hermes on two VMs later:

1. Point both at the **same** Valkey / Postgres / Qdrant hosts.
2. Share `HERMES_SHARED_DATA` (or NFS) so `zalo_owner` remains a cluster singleton.
3. Run `zalo-proxy` / bridge on **one** node only.
4. Keep Model Router + 9router / OmniRouter reachable from both Hermes instances.

Do **not** call this HA until stores are replicated.
