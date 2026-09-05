# Case 74: Failure Injection Coverage Gate

**Gap matrix id:** Case 70 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Prevent the test suite itself from developing blind spots.

For every production component, require at least:

- happy path;
- invalid input;
- dependency unavailable;
- timeout;
- malformed response;
- restart during operation;
- duplicate request;
- recovery;
- concurrency;
- persistence verification.

## Required coverage matrix

| Component | Happy | Invalid | Timeout | Crash | Duplicate | Recovery | Concurrent |
|---|---|---|---|---|---|---|---|
| Hermes | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Model Router | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| OmniRoute | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| OmniRoute | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Valkey | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| PostgreSQL | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Qdrant | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Workflow | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Dispatcher | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| OCR | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Media | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Security | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Zalo | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Schedule | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Backup | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

A blank cell means **test gap**, not "not applicable", unless the case explicitly documents why.

---

# Final Production Acceptance Rule

The stack must NOT be considered production-ready merely because all existing cases 01–35 pass.

A release should require:

```text
Existing functional suite
        +
Failure injection suite
        +
Recovery suite
        +
Concurrency suite
        +
Persistence consistency
        +
Security isolation
        +
Soak/chaos test
```

The strongest acceptance criterion is:

> Every injected failure must produce a bounded failure, preserve unrelated work, preserve required persistent state, avoid duplicate side effects, recover automatically when designed, and leave enough evidence for an operator to diagnose the incident.

## Recommended New Files

Add:

```text
test/cases/
  36-dependency-failure-matrix.md
  37-restart-inflight.md
  38-idempotency-duplicates.md
  39-outbox-lease-recovery.md
  40-poison-job.md
  41-retry-backoff.md
  42-malformed-llm-response.md
  43-router-combo-failure.md
  44-valkey-session-failure.md
  45-postgres-memory-failure.md
  46-qdrant-failure.md
  47-attachment-partial-failure.md
  48-ocr-blind-model.md
  49-watchdog-false-positive.md
  50-queue-fairness.md
  51-zalo-sse-recovery.md
  52-zalo-delivery-failure.md
  53-schedule-crash-boundary.md
  54-schedule-clock-anomalies.md
  55-backup-corruption.md
  56-resource-exhaustion.md
  57-permission-drift.md
  58-config-corruption.md
  59-edge-security-regression.md
  60-prompt-injection-boundaries.md
  61-cross-user-isolation.md
  62-session-reset-recovery.md
  63-router-backpressure.md
  64-long-running-soak.md
  65-chaos-combination.md
  66-full-stack-recovery.md
  67-update-persistence.md
  68-input-fuzzing.md
  69-error-classification.md
  70-failure-coverage-gate.md
```

## Important implementation rule

Do **not** make one giant `test-all.sh` that simply executes these cases sequentially.

The test runner should distinguish:

```text
UNIT
INTEGRATION
E2E
FAILURE-INJECTION
RECOVERY
CONCURRENCY
CHAOS
SOAK
```

and each failure-injection test should have a deterministic way to inject and remove the fault.

That prevents the testing command itself from becoming another source of false confidence.
