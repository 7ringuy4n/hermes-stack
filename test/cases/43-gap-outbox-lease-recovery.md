# Case 43: Outbox / Lease Recovery

**Gap matrix id:** Case 39 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Validate the Postgres canonical workflow + outbox + lease design under worker crashes.

The current architecture intentionally uses Postgres as canonical state while Valkey delivers work, with outbox/leases/idempotency recovering stalled work.

## Procedure

1. Create 10 workflow jobs.
2. Allow worker to claim job #1.
3. Kill worker before completion.
4. Leave lease expired.
5. Restart worker.
6. Observe job #1.
7. Repeat while:
   - output is partially generated;
   - notification has already been sent;
   - DB update has completed but ACK has not;
   - ACK occurs but process crashes immediately afterward.

## Pass criteria

- No permanently leased job.
- No lost job.
- No uncontrolled duplicate side effect.
- Job eventually reaches terminal state.
- Outbox is drained.
- Postgres and Valkey agree on executable state.

---
