# notification

## System architecture

| | |
|--|--|
| **Sits between** | ingest / security / zalo-api ↔ admin channel |
| **Owns** | `POST /v1/notify` delivery |
| **Does not own** | End-user chat replies |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">ingest / security / zalo-api</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>notify</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">Admin DM / channel</td>
  </tr>
</table>

## Purpose

NotificationManager: push short admin alerts (learn events, security probes, ops summaries) to a configured channel (often Zalo DM) without interrupting the end-user chat turn.

## Profile

Optional notification worker (`ENABLE_NOTIFY=active`).

## Sub-packages

| Package | Function |
|---|---|
| [notify/](./notify/README.md) | `POST /v1/notify` — title/body/severity/channels |

## How it works

```text
ingest / security / zalo-api / alert-watch
    → POST notify /v1/notify or /v1/alert
    → Zalo dest: request thread, else NOTIFY_ZALO_THREAD (override),
      else sole admin in `zalo_admin_users.txt` / `ZALO_ADMIN_USERS`
    → user chat stays clean (no “saved” spam)
```

`NOTIFY_ZALO_THREAD` is optional. When empty, alerts go to the **current sole Zalo admin** (file is re-read on each send, so `!zalo claim` / `!zalo admin transfer` apply without restarting notify). Health: `zalo_thread` + `zalo_dest_source` (`override` | `admin_file` | `admin_env` | `none`) — never the uid.

Zalo cannot DM the same account that scanned the QR (bridge `ownId`). If the sole admin is still that placeholder, run `!zalo claim` from a personal Zalo so alerts land in a human inbox.

Copy for learn alerts: editable `hermes/main/messages/learn-notify.json`.

## Related

- [tools/ingest](../tools/ingest/README.md)  
- [zalo-api](../zalo-api/README.md)  
- [hermes/main/messages](../../hermes/main/messages/README.md)
