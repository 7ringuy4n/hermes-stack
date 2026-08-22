# Case 54: Queue Ordering / Fairness

**Gap matrix id:** Case 50 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Detect starvation and incorrect FIFO behavior.

## Procedure

Create queues containing:

- 20 Hermes jobs;
- 20 Zalo jobs;
- 20 media jobs;
- 20 workflow jobs.

Mix them randomly.

Repeat with:

- one very slow job;
- many fast jobs;
- one permanently failing job.

## Pass criteria

- One queue type cannot starve another.
- Per-thread FIFO remains correct.
- Slow job does not block independent work.
- Failed job does not block subsequent jobs.

This is especially important because the current changelog already records a mixed Valkey queue starvation bug.

---
