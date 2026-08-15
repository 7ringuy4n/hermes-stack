# authentication

## Purpose

Identity, workspace membership, roles, and policy evaluation **before** the agent runs privileged tools or RAG on protected knowledge. Default deny for workspace access on High.

## Profile

| Profile | State |
|---|---|
| Low / Medium | Off (no authz gate on every chat turn) |
| High | On — `ENABLE_AUTHZ=1`, optional `ENABLE_POLICY=1` |

## Sub-packages

| Package | Function |
|---|---|
| [authz/](./authz/README.md) | Authorize principal + workspace; ACL tables in Postgres |
| [policy-center/](./policy-center/README.md) | Extra policy rules / evaluations (High) |

## How it works (High)

```text
Inbound message
    → resolve external user id → internal principal
    → workspace ACL (default DENY)
    → role / permission
    → resource ACL (which knowledge)
    → ALLOW → Hermes
    → DENY  → stop (no RAG, no tools)
```

## Default admin (High setup)

- Create non-deletable **admin** user in the secret store / `.env` (never print password into chat).
- Admins join group/role **`admin`**; new users default role **`user`**.

## Related

- [security](../security/README.md)  
- [docs/00-profiles.md](../../docs/00-profiles.md)
