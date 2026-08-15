# authentication / authz

## Purpose

HTTP service that answers “may this principal act in this workspace / on this resource?” Postgres is the source of truth for membership and ACL rows.

## Profile

High (`ENABLE_AUTHZ=1`).

## Main functions

| Function | Detail |
|---|---|
| Authorize | Input: user/thread/workspace → allow/deny |
| Membership | Users belong to workspaces with roles |
| Knowledge scope | Which document collections a role may search |
| Audit hooks | Record denials for SIEM (High) |

## Ports (typical)

`8100`-adjacent lab used `8097` — keep `AUTHZ_URL=http://authz:8097` in compose when enabled.

## Related

- [../README.md](../README.md)  
- [policy-center](../policy-center/README.md)
