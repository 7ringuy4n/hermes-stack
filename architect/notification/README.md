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

High (`ENABLE_NOTIFY=1`). Off on Low/Medium by default.

## Sub-packages

| Package | Function |
|---|---|
| [notify/](./notify/README.md) | `POST /v1/notify` — title/body/severity/channels |

## How it works

```text
ingest / security / zalo-api
    → POST notify /v1/notify
    → deliver to admin thread (env NOTIFY_ZALO_THREAD)
    → user chat stays clean (no “saved” spam)
```

Copy for learn alerts: editable `hermes/main/messages/learn-notify.json`.

## Related

- [tools/ingest](../tools/ingest/README.md)  
- [zalo-api](../zalo-api/README.md)  
- [hermes/main/messages](../../hermes/main/messages/README.md)
