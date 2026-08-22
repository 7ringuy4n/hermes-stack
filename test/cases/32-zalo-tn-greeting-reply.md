# Case: Zalo DM greeting gets a reply (Tn inject)

Simulate a real Zalo inbound for admin user **Tn** via the bridge
(`POST /inject-event`), then expect Hermes to reply on the same DM thread.

## Goal

Catch “no response” regressions on short Vietnamese greetings (chat-only, no tools).

## Preconditions

- Bridge logged in, Hermes SSE connected (`sseClients >= 1`)
- Tn present in `zalo_admin_users.txt` (id|Tn)
- Omni combo `hermes` has at least one healthy chat model

## Steps

1. Run `python test/scripts/zalo_tn_greeting_inject.py`
2. Script resolves Tn’s Zalo user id from the allowlist file (never hardcodes the id in git).
3. Injects text `chúc một buổi sáng tốt lành` as a user DM onto the bridge SSE fan-out.
4. Waits for Hermes inbound log + outbound `Zalo: send ok` (or equivalent send success).

## Pass criteria

| Check | Pass |
|-------|------|
| Inject HTTP ok | yes |
| Hermes sees inbound for Tn thread | within 15s |
| Hermes sends a reply | within 60s |
| No `queue turn timeout` for that inject | yes |

## Fail events

- Inject 404 / bridge down
- Inbound seen but no outbound within 60s
- Queue turn timeout on the greeting thread
- Hermes / bridge crash-loop during the run

## Notes

- Uses the same path as a phone message (bridge → Hermes SSE), not Traefik chat.
- Display name default `Tn`; override with `ZALO_TEST_USER_NAME`.
- Text override: `ZALO_GREETING_TEXT`.
