# notification

## Purpose

NotificationManager: push short admin alerts (learn events, security probes, ops summaries) to a configured channel (often Zalo DM) without interrupting the end-user chat turn.

## Profile

High (`ENABLE_NOTIFY=1`). Off on Low/Medium by default.

## Sub-packages

| Package | Function |
|---|---|
| [notify/](./notify/README.md) | `POST /v1/notify` — title/body/severity/channels |

## How it works

```text
ingest / security / admin-api
    → POST notify /v1/notify
    → deliver to admin thread (env NOTIFY_ZALO_THREAD)
    → user chat stays clean (no “saved” spam)
```

Copy for learn alerts: editable `hermes/main/messages/learn-notify.json`.

## Related

- [tools/ingest](../tools/ingest/README.md)  
- [hermes/main/messages](../../hermes/main/messages/README.md)
