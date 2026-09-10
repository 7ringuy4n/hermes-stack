# Case 57: Schedule Crash Boundary

**Gap matrix id:** Case 53 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test every possible crash point around scheduled execution.

## Procedure

For a scheduled job:

1. Crash before job creation.
2. Crash after job creation.
3. Crash after lease.
4. Crash after execution starts.
5. Crash after execution completes.
6. Crash after result persistence.
7. Crash after Zalo delivery.
8. Crash before acknowledgement.

Repeat for:

- once;
- daily;
- weekly;
- monthly;
- yearly.

## Pass criteria

- Once jobs never fire twice.
- Recurring jobs retain correct next-run state.
- No missed execution caused by a tiny timing window.
- No duplicate outbound message.
- Stale lease eventually recovers.

---
