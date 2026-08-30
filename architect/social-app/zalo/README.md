# social-app / zalo

## Purpose

Detachable Zalo channel: receive messages, fetch media, send replies, and (optionally) admin commands. Hermes stays social-agnostic; this pack is the Zalo-specific edge.

## Attribution

Host bridge and original adapter design: **[hermes-zalo-plugin](https://github.com/cuongdev/hermes-zalo-plugin)** by **Cường Tuấn Nguyễn** ([cuongdev](https://github.com/cuongdev)), MIT License.

Assistant **reuses** that project and **optimizes** attach for the current workflow (profile-ready install, `zalo-proxy`, manual login last). See `hermes/main/plugins/zalo/ATTRIBUTION.md`.

## Profile

Off by default. Attach with `ENABLE_ZALO=active`. Not part of Low Must.

## Install order

1. Stack for current `ASSISTANT_PROFILE` is up and healthy.
2. `bash scripts/main/setup-zalo.sh` — bridge + adapter + proxy (no login).
3. Operator runs **`bash scripts/main/login-zalo.sh`** (QR) — never automated in deploy.

## Admin (exactly one user)

1. `login-zalo` seeds sole admin = bridge `ownId` (account that logged into Zalo proxy).
2. From your **personal** Zalo, DM the bot: `!zalo claim` (takes admin when seed is still the bridge account).
3. Transfer later: `!zalo admin transfer @tag` / reply / `<uid>` — still only one admin.

Also: `!zalo admin` · `!zalo whoami`

## Components

| Piece | Function |
|---|---|
| Host bridge | Upstream `hermes-zalo-plugin` (zca-js) on `:8787` |
| `zalo-proxy` | Compose profile → Docker reaches host bridge |
| Adapter | `hermes/main/plugins/zalo` |

## Related

- [../README.md](../README.md)
- [hermes/main/plugins/zalo](../../../hermes/main/plugins/zalo/README.md)
