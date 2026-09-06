# Project history

This file is the stable navigation point for project history.

- Root-cause records are maintained by date under [`history/`](../history/README.md).
- Operational changes and incident pointers are indexed in [`scripts/HISTORY.md`](../scripts/HISTORY.md).
- Release-facing changes are recorded in [`docs/CHANGELOG.md`](./CHANGELOG.md).

History entries must describe reusable symptoms, causes, decisions, fixes,
verification, and prevention. Do not copy chat messages, credentials, host
identities, or ticket-specific wording into documentation.

## 2026-09-06 — scoped notes and request control

See `history/2026-09-06/README.md` for the durable note boundary, semantic
active-turn cancellation, healthy Zalo standby behavior, and OpenBao-backed
retention defaults. The same record covers the atomic task-aware proxy rename
to Router Worker and its upgrade cleanup boundary. It also records the verified
teardown requirement: transient OpenBao values are reloaded before backup and
Compose parsing, and an incomplete OmniRoute inventory blocks destruction.

## 2026-09-05 — update isolation, routing consolidation, and Zalo HA

See `history/2026-09-05/README.md` for the update/watchdog race, transient
OpenBao secret propagation, retired routing cleanup, dependency replacement,
scheduled media plan handoff, grounded image composition, stale Zalo SSE recovery,
image-edit routing, quoted-media ownership, slow-provider resilience,
single-deliverable visual documents, and the
model-authored office-artifact release gate, and Traefik-routed Zalo ownership
with renewable Valkey failover.
