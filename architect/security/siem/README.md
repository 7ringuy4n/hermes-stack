# security / siem

## Purpose

Collect security-relevant events (authz deny, AV block, secret-probe hit) for operators. v1 may be a thin forwarder or API; expand without blocking Low chat path.

## Profile

High (`ENABLE_SIEM=active`).

## Main functions

| Function | Detail |
|---|---|
| Ingest events | JSON events from other services |
| Store / forward | Local log, webhook, or future SIEM backend |

## Related

- [../README.md](../README.md)  
- [notification](../../notification/README.md)
