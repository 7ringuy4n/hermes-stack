# Verification

[`RULES.md`](./RULES.md) is the release-verification contract. It combines
offline regressions, a clean VPS lifecycle gate, real Zalo outcomes, artifact
evaluation, DM/group concurrency, owner failover, and post-run stability.

## Layout

| Path | Purpose |
|---|---|
| [`RULES.md`](./RULES.md) | Required evidence, outcomes, capability cases, and merge gate. |
| [`SETUP.local.md`](./SETUP.local.md) | From-scratch setup, full restore, and the supported partial-recovery boundary. |
| [`cases/`](./cases/) | Durable scenario specifications and historical gap cases. |
| [`scripts/`](./scripts/) | Offline units and authorized lab drivers. |
| `reports/` | Sanitized generated evidence; never credentials or personal identifiers. |

Run the batch gate with `test/scripts/run_case_index_lab.py`. It discovers all
`*_unit.py` files, then runs the curated live list unless `SKIP_VPS=1` is set.
A successful process or assertion is insufficient for Zalo/media/office cases:
the delivered reply or artifact must also be inspected and rated.

The current Zalo HA model has one Valkey-elected SSE owner. Different DM/group
conversations may execute concurrently; one conversation stays FIFO ordered.
Claimed queue items are acknowledged only at a terminal turn and are recovered
by a promoted owner after a process loss.
