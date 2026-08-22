# Case 66: Session Reset / Stale Session Recovery

**Gap matrix id:** Case 62 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test session lifecycle transitions.

## Procedure

Test:

- normal session;
- session expiry;
- explicit reset;
- reset-all;
- Hermes restart;
- Valkey restart;
- session file deletion;
- corrupted session;
- oversized session;
- replica migration.

## Pass criteria

- Old context is not unexpectedly reused.
- New session starts clean.
- Durable memory remains available according to design.
- No cross-user context.
- No session file corruption.

---
