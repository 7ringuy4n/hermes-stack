# Case 45: Retry Storm / Backoff

**Gap matrix id:** Case 41 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Detect uncontrolled retry amplification.

## Procedure

Make an upstream return:

1. 500;
2. 502;
3. 503;
4. 429;
5. timeout;
6. connection reset.

Send 20 concurrent requests.

Observe:

- retry count;
- retry interval;
- upstream request rate;
- CPU;
- memory;
- queue size.

## Pass criteria

- Backoff is bounded.
- No retry storm.
- 429 does not create infinite retries.
- One request cannot multiply into dozens of upstream calls unexpectedly.
- System remains responsive.

---
