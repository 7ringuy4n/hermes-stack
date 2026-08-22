# Case 73: Production Error Classification

**Gap matrix id:** Case 69 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Verify every failure can be classified operationally.

For every injected failure, require one category:

- USER_ERROR
- AUTH_ERROR
- POLICY_DENIED
- DEPENDENCY_UNAVAILABLE
- DEPENDENCY_TIMEOUT
- RATE_LIMITED
- INVALID_MODEL_RESPONSE
- QUEUE_FAILURE
- PERSISTENCE_FAILURE
- DELIVERY_FAILURE
- RESOURCE_EXHAUSTED
- INTERNAL_ERROR

## Pass criteria

A production operator can determine:

1. what failed;
2. where it failed;
3. whether retry is safe;
4. whether user action is required;
5. whether data may have been lost;
6. whether automatic recovery occurred.

---
