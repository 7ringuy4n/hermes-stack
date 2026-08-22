# Case 58: Schedule Time Boundary / Clock Anomalies

**Gap matrix id:** Case 54 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test scheduler behavior around real-world clock problems.

## Inputs

- `00:00`;
- `23:59`;
- current minute;
- 1 minute in the past;
- 1 minute in the future;
- same-minute creation;
- daylight-saving transition simulation where applicable;
- timezone change;
- host clock jump forward;
- host clock jump backward;
- duplicate schedule submission.

## Pass criteria

- Correct timezone.
- No duplicate fire.
- No unexpected next-day jump.
- Catch-up behavior follows product policy.
- Re-upsert does not accidentally erase a due execution.

This extends the recent same-minute cron fixes rather than merely repeating the existing timezone case.

---
