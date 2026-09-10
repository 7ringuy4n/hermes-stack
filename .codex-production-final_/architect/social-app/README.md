# social-app

## System architecture

| | |
|--|--|
| **Sits between** | Messaging platforms ↔ Hermes plugins |
| **Owns** | Channel packs (normalize inbound, media fetch, admin commands in-pack) |
| **Does not own** | Agent skills / LTM (Hermes + memory) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Zalo / Telegram / HTTP</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>social-app pack</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">Hermes → reply</td>
  </tr>
</table>

## Purpose

Optional **chat front-ends** that sit in front of Hermes. Attach Zalo, Telegram, or HTTP when needed; they are workers/components, not product tiers.

## Profile

| Pack | When |
|---|---|
| None | Core console/HTTP only |
| `ENABLE_ZALO=active` / Telegram / HTTP | Explicit attach |

## Sub-packages

| Folder | Function |
|---|---|
| [zalo/](./zalo/README.md) | Zalo bridge + admin commands (detachable) |
| [telegram/](./telegram/README.md) | Telegram bot bridge (stub) |
| [http/](./http/README.md) | Generic HTTP / webhook channel (stub) |

## How it works

```text
User on Zalo/Telegram/HTTP
        │
        ▼
 social-app pack (normalize message, media fetch)
        │
        ▼
 Hermes Agent  (+ hermes/main/plugins/<app> adapter code)
        │
        ▼
 Reply back through the same pack
```

- **Admin features** (e.g. learn overrides) stay **inside** the pack so removing the pack removes those commands.
- UX strings belong in `hermes/main/messages/`, not hardcoded forever in adapters.
- WhatsApp is **not** shipped.

## Related

- [hermes/main/plugins](../../hermes/main/plugins/README.md)  
- [notification](../notification/README.md) — optional admin DMs
- [zalo-api](../zalo-api/README.md) — Zalo channel admin HTTP
