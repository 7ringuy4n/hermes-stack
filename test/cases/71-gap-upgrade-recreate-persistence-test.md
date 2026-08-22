# Case 71: Upgrade / Recreate Persistence Test

**Gap matrix id:** Case 67 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Detect state loss during normal deployment.

## Procedure

1. Create:
   - sessions;
   - durable memory;
   - Qdrant knowledge;
   - schedules;
   - workflow jobs.
2. Run:
   `bash run.sh update`
3. Restart.
4. Recreate affected workers.
5. Verify all state.

Repeat with:

- Hermes ×1 → ×2;
- worker inactive → active;
- worker active → inactive.

## Pass criteria

Persistent state survives expected deployment operations.

No old jobs unexpectedly reappear.

No previously deleted schedule is resurrected.

---
