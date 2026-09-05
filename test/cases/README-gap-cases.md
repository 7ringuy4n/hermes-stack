# Production failure gap cases (v2)

Source: operator gap matrix extending cases 01–37.

Lab scripts that need a Zalo user must inject as allowlisted **Tn** via bridge /inject-event (id from host allowlist — never commit).

| Case | File | Title |
|------|------|-------|
| 40 | 40-gap-dependency-failure-matrix.md | Dependency Failure Matrix |
| 41 | 41-gap-restart-during-in-flight-request.md | Restart During In-Flight Request |
| 42 | 42-gap-duplicate-delivery-idempotency.md | Duplicate Delivery / Idempotency |
| 43 | 43-gap-outbox-lease-recovery.md | Outbox / Lease Recovery |
| 44 | 44-gap-poison-job-permanently-failing-job.md | Poison Job / Permanently Failing Job |
| 45 | 45-gap-retry-storm-backoff.md | Retry Storm / Backoff |
| 46 | 46-gap-malformed-llm-response-matrix.md | Malformed LLM Response Matrix |
| 47 | 47-gap-omniroute-combo-failure.md | OmniRoute Combo Failure |
| 48 | 48-gap-valkey-failure-session-consistency.md | Valkey Failure / Session Consistency |
| 49 | 49-gap-postgresql-failure-memory-write-race.md | PostgreSQL Failure / Memory Write Race |
| 50 | 50-gap-qdrant-failure-knowledge-consistency.md | Qdrant Failure / Knowledge Consistency |
| 51 | 51-gap-attachment-pipeline-partial-failure.md | Attachment Pipeline Partial Failure |
| 52 | 52-gap-ocr-false-positive-blind-vision-regression.md | OCR False-Positive / Blind Vision Regression |
| 53 | 53-gap-watchdog-false-positive.md | Watchdog False Positive |
| 54 | 54-gap-queue-ordering-fairness.md | Queue Ordering / Fairness |
| 55 | 55-gap-zalo-sse-disconnect-reconnect.md | Zalo SSE Disconnect / Reconnect |
| 56 | 56-gap-zalo-outbound-failure-after-successful-processing.md | Zalo Outbound Failure After Successful Processing |
| 57 | 57-gap-schedule-crash-boundary.md | Schedule Crash Boundary |
| 58 | 58-gap-schedule-time-boundary-clock-anomalies.md | Schedule Time Boundary / Clock Anomalies |
| 59 | 59-gap-backup-corruption-partial-backup.md | Backup Corruption / Partial Backup |
| 60 | 60-gap-disk-full-resource-exhaustion.md | Disk Full / Resource Exhaustion |
| 61 | 61-gap-permission-ownership-drift.md | Permission / Ownership Drift |
| 62 | 62-gap-configuration-corruption.md | Configuration Corruption |
| 63 | 63-gap-public-local-security-regression.md | Public / Local Security Regression |
| 64 | 64-gap-prompt-injection-through-every-data-boundary.md | Prompt Injection Through Every Data Boundary |
| 65 | 65-gap-cross-user-cross-thread-isolation.md | Cross-User / Cross-Thread Isolation |
| 66 | 66-gap-session-reset-stale-session-recovery.md | Session Reset / Stale Session Recovery |
| 67 | 67-gap-model-router-edge-backpressure.md | Model Router / Edge Backpressure |
| 68 | 68-gap-long-running-soak-test.md | Long-Running Soak Test |
| 69 | 69-gap-chaos-combination-test.md | Chaos Combination Test |
| 70 | 70-gap-recovery-after-full-dependency-restart.md | Recovery After Full Dependency Restart |
| 71 | 71-gap-upgrade-recreate-persistence-test.md | Upgrade / Recreate Persistence Test |
| 72 | 72-gap-unknown-input-fuzzing.md | Unknown Input Fuzzing |
| 73 | 73-gap-production-error-classification.md | Production Error Classification |
| 74 | 74-gap-failure-injection-coverage-gate.md | Failure Injection Coverage Gate |
