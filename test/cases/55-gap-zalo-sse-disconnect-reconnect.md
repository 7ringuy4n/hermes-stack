# Case 55: Zalo SSE Disconnect / Reconnect

**Gap matrix id:** Case 51 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test the single-owner Zalo SSE model under network failures.

## Procedure

1. Start Zalo.
2. Confirm exactly one SSE owner.
3. Disconnect network.
4. Restore network.
5. Kill Zalo proxy.
6. Kill Zalo API.
7. Restart both.
8. Send messages during outage.
9. Send messages immediately after reconnect.

## Pass criteria

- Exactly one SSE owner.
- No second SSE client.
- No duplicate inbound messages.
- Queued messages are handled according to policy.
- QR is not requested unnecessarily when session remains valid.
- Session-dead state requires operator login only when actually dead.

---
