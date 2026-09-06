# zalo-api

## System architecture

| | |
|--|--|
| **Sits between** | Zalo pack / bridge ↔ allowlists & `!zalo` actions |
| **Owns** | `POST /v1/zalo/chat`, Zalo-scoped admin HTTP |
| **Does not own** | SSE ownership (host bridge + `zalo_owner` lock) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Zalo pack / !zalo</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>zalo-api</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">bridge → proxy → Hermes</td>
  </tr>
</table>

## Purpose

HTTP API for Zalo channel admin: allowlists, learn helpers, and in-Zalo `!zalo …` commands (`/v1/zalo/chat`). Keeps privileged mutations out of the Hermes prompt path.

## When it runs

Started **only** with Zalo (`ENABLE_ZALO=active` → compose profile `zalo`), alongside `zalo-proxy`. Not tied to Low/Medium/High profile flags.

## Main functions

| Area | Function |
|---|---|
| In-Zalo | `!zalo claim` / allow / kick / learn / `!zalo schedule` CRUD (`list` = this chat; `list all` = every chat; `update` accepts `--time`, `--`, or `Tên : payload`) / … via `POST /v1/zalo/chat` |
| Allowlists | Approve users / threads |
| Health | `/health` |

## Env

- `ZALO_API_TOKEN` (Bearer) — required in production
- `ZALO_BRIDGE_URL` / `ZALO_PLUGIN_TOKEN` — reach host `hermes-zalo-plugin`
- Hermes: `ZALO_API_URL=http://zalo-api:8100`

## Related

- [social-app/zalo](../social-app/zalo/README.md)
- [plugins/zalo](../../hermes/main/plugins/zalo/README.md)
- [notification](../notification/README.md)
