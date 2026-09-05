# Case 40: Dependency Failure Matrix

**Gap matrix id:** Case 36 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Verify Hermes behaves correctly when each core dependency disappears independently.

## Dependencies

Test each independently:

- Valkey
- PostgreSQL
- Qdrant
- model-router
- OmniRoute
- OmniRoute
- workflow
- dispatcher
- OCR
- media worker
- Zalo API
- Zalo proxy
- Traefik
- OpenVPN
- Security Worker
- notification worker

## Procedure

For each dependency:

1. Start the complete stack.
2. Verify normal request succeeds.
3. Stop only the selected dependency.
4. Send the operation that requires it.
5. Record response.
6. Verify Hermes does not crash.
7. Verify unrelated operations still work.
8. Restart the dependency.
9. Wait for health recovery.
10. Repeat the original request.

## Pass criteria

- Expected operation fails gracefully.
- No crash-loop.
- No unrelated service is restarted unnecessarily.
- No infinite retry loop.
- Recovery occurs automatically where designed.
- Subsequent request succeeds.
- No duplicate response/job is generated.

## Important

Do not test only:

`dependency DOWN → request FAIL`

Also test:

`dependency DOWN → request starts → dependency DOWN → dependency UP → request finishes`

This catches race conditions hidden by ordinary failure tests.

---
