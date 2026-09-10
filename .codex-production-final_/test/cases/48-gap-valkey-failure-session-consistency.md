# Case 48: Valkey Failure / Session Consistency

**Gap matrix id:** Case 44 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test the current decision that Valkey is short-term session memory, locks, and queues.

## Procedure

### A

Start conversation:

1. message A
2. message B
3. stop Valkey
4. send message C

### B

Restart Valkey while Hermes is processing.

### C

Flush only the test session.

### D

Create two concurrent requests for the same session.

### E

Create concurrent requests for two different sessions.

## Pass criteria

- No cross-session contamination.
- Same-session ordering remains correct where required.
- Different sessions remain independent.
- Valkey recovery does not corrupt Postgres durable memory.
- Hermes does not claim memory exists when it is unavailable.

---
