# hermes / messages

## Purpose

**Editable** user-facing and admin-facing copy so operators can improve UX without patching adapter code.

## Files

| File | Function |
|---|---|
| `learn-notify.json` | Knowledge pending/approved/deleted notify templates (`from={id}|{name}`) |
| `ux.json` | Cite empty/ingest-down, secret-probe refuse, etc. |

## Rules

- UTF-8 always (Vietnamese supported)
- Services/skills load by path/env (e.g. `LEARN_NOTIFY_PATH`)
- Do not embed long paragraphs in Python adapters

## Related

- [skills](../skills/README.md)  
- [architect/notification](../../architect/notification/README.md)
