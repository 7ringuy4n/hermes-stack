# Case 56: Zalo Outbound Failure After Successful Processing

**Gap matrix id:** Case 52 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Detect duplicate replies when Hermes successfully processes a request but Zalo delivery fails.

## Procedure

1. Process a request successfully.
2. Make Zalo `/send` fail after Hermes has produced the response.
3. Restore Zalo.
4. Trigger retry/recovery.

Repeat with:

- timeout;
- 500;
- connection reset;
- invalid attachment;
- text fallback.

## Pass criteria

The same response must not be delivered twice unless retry policy explicitly requires it and the delivery operation is idempotent.

---
