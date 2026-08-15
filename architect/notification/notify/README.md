# notification / notify

## Purpose

HTTP notification service. Accepts structured alerts and fans out to log and/or social DM.

## Profile

High.

## Main functions

| API | Function |
|---|---|
| `POST /v1/notify` | `{ title, body, severity, channels, kind }` |
| `POST /v1/summary` | Longer digest (e.g. weekly ops) |

## Related

- [../README.md](../README.md)
