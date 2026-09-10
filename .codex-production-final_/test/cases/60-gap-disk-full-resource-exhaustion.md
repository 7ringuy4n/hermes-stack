# Case 60: Disk Full / Resource Exhaustion

**Gap matrix id:** Case 56 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test production behavior when the host runs out of resources.

## Simulate

- disk nearly full;
- inode exhaustion;
- memory pressure;
- CPU saturation;
- Docker storage exhaustion;
- media volume full;
- backup volume full;
- Postgres volume full.

## Pass criteria

- No silent data corruption.
- No endless restart loop.
- User gets controlled failure.
- Existing requests finish where possible.
- Critical stores remain recoverable.
- Watchdog does not amplify the incident.

---
