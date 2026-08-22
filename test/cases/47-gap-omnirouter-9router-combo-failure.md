# Case 47: OmniRouter / 9Router Combo Failure

**Gap matrix id:** Case 43 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Validate routing when a configured combo is empty, invalid, unavailable, or partially unavailable.

## Matrix

Test:

- combo exists;
- combo empty;
- combo contains one unavailable model;
- all models unavailable;
- first model 401;
- first model 429;
- first model timeout;
- first model 500;
- second model succeeds;
- provider returns malformed response;
- router restarts during request.

## Pass criteria

- Correct fallback behavior.
- No request hangs indefinitely.
- No model is selected outside configured policy.
- No secret/model configuration leaks to user.
- Recovery after router restart works.

---
