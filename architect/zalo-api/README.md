# zalo-api

## Purpose

HTTP API for Zalo channel admin: allowlists, learn helpers, and in-Zalo `!zalo …` commands (`/v1/zalo/chat`). Keeps privileged mutations out of the Hermes prompt path.

## When it runs

Started **only** with Zalo (`ENABLE_ZALO=1` → compose profile `zalo`), alongside `zalo-proxy`. Not tied to Low/Medium/High profile flags.

## Main functions

| Area | Function |
|---|---|
| In-Zalo | `!zalo claim` / allow / kick / learn / … via `POST /v1/zalo/chat` |
| Allowlists | Approve users / threads |
| Health | `/health` |

## Env

- `ZALO_API_TOKEN` (Bearer) — required in production (`ADMIN_API_TOKEN` still accepted as alias)
- `ZALO_BRIDGE_URL` / `ZALO_PLUGIN_TOKEN` — reach host `hermes-zalo-plugin`
- Hermes: `ZALO_API_URL=http://zalo-api:8100`

## Related

- [social-app/zalo](../social-app/zalo/README.md)
- [plugins/zalo](../../hermes/main/plugins/zalo/README.md)
- [notification](../notification/README.md)
