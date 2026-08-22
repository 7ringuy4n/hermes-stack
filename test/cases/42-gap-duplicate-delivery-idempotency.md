# Case 42: Duplicate Delivery / Idempotency

**Gap matrix id:** Case 38 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Ensure retries and duplicated inbound events cannot create duplicate side effects.

## Procedure

Send the same logical request twice with the same event/request identifier.

Test:

- normal Zalo message;
- file upload;
- schedule creation;
- schedule execution;
- workflow job;
- generated file;
- generated image;
- notification;
- memory write.

Repeat with:

- exact duplicate;
- duplicate after 1 second;
- duplicate after 30 seconds;
- duplicate after worker restart.

## Pass criteria

Operations requiring idempotency execute exactly once.

Examples:

- one schedule;
- one generated attachment;
- one outbound message;
- one memory record;
- one workflow side effect.

---
