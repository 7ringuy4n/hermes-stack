# social-app

## Purpose

Optional **chat front-ends** that sit in front of Hermes. A social app is **not** a profile. Low can run with only Hermes console / IDE; attach Zalo, Telegram, or HTTP when you want messaging platforms.

## Profile

| Pack | When |
|---|---|
| None | Low default |
| `ENABLE_ZALO=1` / Telegram / HTTP | Explicit attach |

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
- [notification](../notification/README.md) — High admin DMs  
- [admin-api](../admin-api/README.md)
