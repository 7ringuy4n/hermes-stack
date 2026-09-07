# Case 75 — Zalo continuous-message correlation

Follow C11 in `test/RULES.md`. Send consecutive natural messages without
waiting for prior responses in both an authorized DM and addressed group.
Include a real quote reply, a contextual follow-up, and an unrelated request.

Run:

```bash
python test/scripts/zalo_continuous_messages_lab.py
```

Require per-destination FIFO delivery, one terminal response per accepted
message, correct quote ownership, dequeue-time session continuity, DM/group
isolation, no late timeout response, and a fully drained durable queue. Runtime
identities and bridge message identifiers must not be written to the report.
