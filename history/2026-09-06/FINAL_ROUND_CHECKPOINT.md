# Paused production-final verification checkpoint

Paused by operator request before destructive deployment testing.

## Repository state

- Candidate branch: `fix/zalo/production-final-concurrency`
- Candidate commit: `a0ae154288784ddad9155cc9e92ddf5f110316f8`
- The original operator checkout remains untouched.
- The candidate is pushed; no pull request has been opened or merged.

## Completed

- Read the mandatory rules, changelogs, history, architecture, test contract,
  and core behavior documents.
- Added durable Zalo queue claim/inflight/ack recovery, active-destination
  discovery, owner-task cancellation, stale-worker fencing, and a worker lease
  longer than the maximum queued-turn deadline.
- Added complete Zalo session and identity-policy coverage to verified backups.
- Rebuilt `test/SETUP.local.md`, updated current architecture/test docs, removed
  a fixed live group identity from a scheduler lab, and added DM/group,
  cancellation, backup, and queue-failover verification.
- All locally discovered unit scripts passed with disposable dependencies.
- The VPS was fast-forwarded through current `main`, then switched cleanly to
  the candidate commit. Running containers have not yet been rebuilt from it.
- Baseline services were healthy with zero restart counts in the observed
  snapshot. A new verified full backup contains OpenBao, stores, OmniRoute
  inventory, Zalo session, and identity-policy state with restrictive mode.

## Resume point

1. Resolve the durable group-membership verification using the PostgreSQL role
   from the running container environment; the first read-only probe used an
   incorrect assumed role and changed nothing.
2. Capture sanitized pre-deploy hashes/counts, then run the authorized
   backup-first destroy and clean `up` path.
3. Verify session/login, named three-member group, OmniRoute inventory, one SSE
   owner, timers, stores, and all workers after deployment.
4. Run live DM/group concurrency, quoted cancellation, owner failover, capability
   cases, and one-versus-two-replica observations. Monitor all required logs.
5. Update the dated result record, rerun the complete local gate, clean test
   temporary files, and only then open/merge the authorized requests if every
   required gate passes.

Do not expose credentials, numeric identities, backup contents, or router
tokens in reports. Do not modify operator-managed OmniRoute combo membership.
