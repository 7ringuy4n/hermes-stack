---
name: zalo-context
description: "Look up Zalo user/thread/claim context via zalo-api (PostgreSQL). Use before scheduling or delivering to a named group/DM. Never invent thread ids or substitute user_id for thread_id."
---

# Zalo context

Controlled API for Zalo identity and delivery routing. **Do not** run SQL.
**Do not** guess group ids from display names without calling this skill.

## Base

`ZALO_API_URL` (default `http://zalo-api:8100`) + bearer `ZALO_API_TOKEN` / `ADMIN_API_TOKEN`.

## Operations

### Current context (preferred)

```bash
curl -sS -X POST "$ZALO_API_URL/v1/zalo/context" \
  -H "Authorization: Bearer $ZALO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"<inbound thread_id>","user_id":"<sender user_id>","query":"<optional group name e.g. LC>"}'
```

Returns:

- `user_id` — authorization identity
- `thread_id` / `thread_type` / `display_name` — current conversation
- `delivery_thread_id` — where files/schedule fires must go (`claim.claimed_thread_id` when set)
- `claim.admin_user_id` + `claim.claimed_thread_id`

### Find thread by name/id

```bash
curl -sS -X POST "$ZALO_API_URL/v1/zalo/threads/find" \
  -H "Authorization: Bearer $ZALO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"LC group"}'
```

### Active claim

```bash
curl -sS "$ZALO_API_URL/v1/zalo/claims/active?admin_user_id=<uid>" \
  -H "Authorization: Bearer $ZALO_API_TOKEN"
```

## Must follow

1. **Authorization → `user_id`. Delivery → `thread_id` / `delivery_thread_id`.** Never swap them.
2. If `query` / named group is unknown → tell the user to open that group and run `!zalo allow` (or `!zalo refresh`), then retry. **Do not** ask for raw chat ids. **Do not** silently send to Home/DM instead.
3. **Do not** invent a multi-minute “confirmation wait”. If the group is missing, fail fast with the allow/refresh instruction.
4. Schedule create / file / image / worker output for a claimed group must use `claimed_thread_id` (or resolved group `thread_id`), not the admin’s DM id.
5. Prefer this skill over reading JSON allowlists or guessing from chat history.

## Related

- `schedule` — persist lịch with resolved `origin.thread_id`
- `communication/zalo-channel` — Zalo tone / multi-part UX
- `media-out` — result-only delivery
