# Case 49: PostgreSQL Failure / Memory Write Race

**Gap matrix id:** Case 45 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test asynchronous memory persistence failure.

## Procedure

1. Send a message that produces durable memory.
2. Immediately make Postgres unavailable.
3. Allow Hermes response to complete.
4. Restore PostgreSQL.
5. Observe memory persistence.
6. Repeat with 20 messages.
7. Restart memory worker halfway through.

## Pass criteria

- User response is not unnecessarily blocked by async memory failure.
- Memory is either eventually persisted or explicitly marked failed.
- No partial/corrupt record.
- No duplicate memory records after retry.

---
