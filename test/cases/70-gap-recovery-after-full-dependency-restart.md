# Case 70: Recovery After Full Dependency Restart

**Gap matrix id:** Case 66 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Verify the entire stack can recover after a host-level Docker restart.

## Procedure

1. Populate real test data.
2. Run active requests.
3. Restart Docker / all containers.
4. Wait for stack stabilization.
5. Verify:
   - Postgres;
   - Valkey;
   - Qdrant;
   - workflow;
   - model-router;
   - workers;
   - Hermes;
   - Zalo.
6. Query old memory.
7. Query old knowledge.
8. Execute a new workflow.
9. Execute a new schedule.

## Pass criteria

The stack returns to a usable state without manual database repair.

---
