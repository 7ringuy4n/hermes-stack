# Case 69: Chaos Combination Test

**Gap matrix id:** Case 65 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test failures occurring simultaneously, because production rarely gives only one clean failure.

## Example scenario

While:

- 2 Hermes replicas are running;
- 8 Zalo requests are active;
- media extraction is running;
- 3 schedules are due;

perform:

1. restart model-router;
2. disconnect Valkey for 10 seconds;
3. delay OCR;
4. restart workflow;
5. restore dependencies in random order.

## Pass criteria

After stabilization:

- stack becomes healthy;
- no permanent queue corruption;
- no duplicate schedules;
- no cross-user leakage;
- no duplicate Zalo replies;
- no lost durable data;
- no infinite retries.

---
