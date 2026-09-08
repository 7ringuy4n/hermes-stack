# 2026-09-08 — bounded queue-session recovery

## Symptom

A two-destination concurrency gate accepted both inbound events, but only one
request produced its expected response inside the test window. The other queue
claim remained active while the agent repeatedly called model fallbacks. Its
eventual outbound was a timeout notice rather than the requested answer.

## Cause

The platform handler starts agent execution in a background session task. The
durable queue coroutine waited for that session to become idle, but a failed
idle wait abandoned only the queue-side coroutine. It did not cancel the base
adapter session task. In addition, the queue wrapper caught nested
`TimeoutError` values as though its own outer deadline had expired, producing a
misleading configured-duration message.

## Decision and fix

- Cancel the base adapter session task before releasing a claim whose agent did
  not become idle.
- On the outer queue deadline, cancel the same session defensively.
- Distinguish outer cancellation from nested operation timeouts in logs.
- Keep the recovery notice duration-neutral and free of internal process data.
- Make the live two-destination gate require the expected content as well as one
  source-correlated delivery per destination.
- Reinforce the generic response policy so simple, self-contained requests do
  not invoke unrelated tools because of older context.
- Hydrate short model context from completed user/assistant exchanges only.
  User-only records remain durable but cannot repeatedly re-seed a later turn.
- Remove the older duplicate worker-routing entry and disambiguate the vendored
  code-review skill. A unit contract now rejects duplicate registry names.
- Forward the queued attachment list and attachment-kind signal through the
  early media gate. Previously an image-edit plan returned from that gate
  without its source, so the dispatcher was never called.
- End media labs on externally observable artifact and delivery evidence rather
  than an optional flow-log marker.
- Replace the PDF lab's optional missing extractor with the renderer dependency
  already shipped by the worker, then require text extraction, page rendering,
  and an independent visual evaluation.
- Crop the accidental lower-page void from sparse, text-bearing one-page PDFs.
  The operation is structural and topic-neutral; multi-page, image-only, and
  already balanced pages preserve their original geometry.
- Bind every PostgreSQL readiness probe to the configured database name. A
  role-only probe still reported ready but attempted a connection to a missing
  role-named database every five seconds, obscuring meaningful production logs.
- Regenerate the committed Router Worker classifier fallback from the canonical
  prompt parts and assert exact equivalence in the unit gate. This prevents a
  normal update from rewriting tracked source when a prompt part changes.

## Verification

Verification requires the full local unit suite, a clean VPS lifecycle check,
the two-destination real-channel test, owner failover, queue drain, and a final
log/restart audit. A release must not advance while any of those checks fail.

This release gate completed 103 unit scripts without failure, exercised direct
and quoted cancellation in private and group scopes, delivered eight ordered
messages across two concurrent destinations, retrieved exact records from a
disposable ten-million-row corpus with indexed sub-millisecond queries, and
delivered both a real quoted-image edit and a rendered single-page PDF for
independent visual review.

## Prevention

Future concurrency labs must retain structured evidence for both delivery and
semantic outcome. Any asynchronous layer that waits on a lower-level task must
also define how that task is fenced or cancelled when the wait expires.
Changes to classifier prompt parts must regenerate the committed fallback in
the same change; exact bake equivalence is a release invariant.
