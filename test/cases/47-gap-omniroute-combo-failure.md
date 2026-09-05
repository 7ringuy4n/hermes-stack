# Case 47 — OmniRoute combo failure

## Goal

Verify that one unavailable combo member does not interrupt a live request and
that routing remains observable without changing the operator's saved combo
membership or strategy.

## Gate

- Snapshot all combo membership and strategies before the test.
- Make one test-only member unavailable without editing the saved production combo.
- Send a request through the normal Model Router path.
- Require either a successful later target or a bounded, explicit all-targets-failed response.
- Confirm the combo snapshot is byte-for-byte equivalent after cleanup.
- Confirm stack-watch did not restart unrelated services during the request.

Rate-limited or exhausted free targets are recorded as skipped; they are never
converted into a passing functional result.
