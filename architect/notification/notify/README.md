# notification / notify

## Purpose

HTTP notification service. Accepts structured alerts and fans out to log and/or social DM.

Zalo destination (when `channels` includes `zalo`):

1. Request `zalo_thread_id` if set
2. Else `NOTIFY_ZALO_THREAD` (optional override, including a group)
3. Else sole uid in `ZALO_ADMIN_USERS_FILE` (`zalo_admin_users.txt`)
4. Else first id in `ZALO_ADMIN_USERS`

The admin file is mounted read-only from `HERMES_DATA_DIR`. Empty override is the normal High lab case: alerts follow the current Zalo admin.

## Profile

High.

## Main functions

| API | Function |
|---|---|
| `POST /v1/notify` | `{ title, body, severity, channels, kind }` |
| `POST /v1/summary` | Longer digest (e.g. weekly ops) |

## Related

- [../README.md](../README.md)
