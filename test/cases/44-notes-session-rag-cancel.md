# Case 44 — multipurpose notes, session/RAG continuity, active cancellation

Follow C10 in `test/RULES.md`. Use runtime-provided identities and unique
non-secret markers. Capture classifier plan, scoped database/audit evidence,
session and RAG recall before/after replica replacement and compact, queue
history cancellation events, user-visible Zalo replies, restart deltas, and
late-delivery observation. Run message and quote-reply cancellation in the
authorized DM and group; never claim a group pass from a DM-only probe.

Run the reproducible DM cancellation probe with:

```bash
python test/scripts/zalo_active_cancel_lab.py
```

It requires a runtime-provided test identity, uses a real outbound message ID
for the quote case, verifies both cancellation audit events, and observes the
late-delivery window. A group requires a separately authorized group identity.
