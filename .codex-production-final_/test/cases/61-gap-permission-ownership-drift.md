# Case 61: Permission / Ownership Drift

**Gap matrix id:** Case 57 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Detect permission regressions after restart, recreate, restore, or replica scaling.

## Procedure

Change ownership/permissions of:

- Hermes skills;
- replica skills;
- sessions;
- media/inbound;
- media/out;
- workflow DB;
- cron/jobs;
- backup directory;
- Postgres data;
- Qdrant data.

Then:

1. Restart.
2. Recreate.
3. Scale Hermes ×2.
4. Run real operations.

## Pass criteria

No unexpected:

- `Permission denied`;
- read-only filesystem;
- root-owned output that cannot be delivered;
- replica-specific behavior.

This targets the recent replica skills and media permission failures recorded in the changelog.

---
