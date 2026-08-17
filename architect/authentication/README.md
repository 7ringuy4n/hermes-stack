# authentication

## System architecture

| | |
|--|--|
| **Sits between** | Inbound principal ↔ Hermes / RAG |
| **Owns** | Authz ACL (Postgres), optional policy-center |
| **Does not own** | Gateway API keys (edge) or secrets store (OpenBao) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Inbound</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>authz ± policy</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">ALLOW → Hermes · DENY → stop</td>
  </tr>
</table>

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
