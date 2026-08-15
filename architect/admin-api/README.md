# admin-api

## Purpose

HTTP Admin API for operators: allowlists, learn decide helpers, and channel-admin actions when a social-app is attached. Keeps privileged mutations out of the Hermes prompt path.

## Profile

High / when channel admin is enabled (`ENABLE_ADMIN_API=1`).

## Main functions

| Area | Function |
|---|---|
| Allowlists | Approve users for a channel |
| Learn | list / find / delete / approve overrides (pack-dependent) |
| Health | `/health` |

## Design rule

Zalo-specific command parsing belongs with `architect/social-app/zalo` calling this API — so detaching Zalo removes the command surface.

## Related

- [social-app/zalo](../social-app/zalo/README.md)  
- [notification](../notification/README.md)  
- [authentication](../authentication/README.md)
