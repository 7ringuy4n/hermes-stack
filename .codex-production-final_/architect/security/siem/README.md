# security / siem

## Purpose

Collect security-relevant events (authz deny, AV block, secret-probe hit) for operators. Keep this optional path from blocking core chat.

## Profile

Optional SIEM component (`ENABLE_SIEM=active`).

## Main functions

| Function | Detail |
|---|---|
| Ingest events | JSON events from other services |
| Store / forward | Local log, webhook, or future SIEM backend |

## Related

- [../README.md](../README.md)  
- [notification](../../notification/README.md)
