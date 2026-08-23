# Attribution — Zalo bridge & adapter

## Original work

| Item | Detail |
|---|---|
| Project | [hermes-zalo-plugin](https://github.com/cuongdev/hermes-zalo-plugin) |
| Author | **Cường Tuấn Nguyễn** ([cuongdev](https://github.com/cuongdev)) |
| License | MIT — Copyright (c) 2026 Cường Tuấn Nguyễn |
| npm | `hermes-zalo-plugin` |

The host bridge (Node + zca-js) and the original Hermes-side adapter design come from that project.

## This repository

Paths under `hermes/main/plugins/zalo/` and `architect/social-app/zalo/` **reuse** that work (via assistant → assistant) and **optimize** it for the assistant stack:

- Compose profile `zalo` + `zalo-proxy` (Docker → host `:8787`)
- Install only after profile services are healthy
- **Manual** QR login as a separate last step (`scripts/main/login-zalo.sh`)
- Mention-gate / Valkey / admin-command patches for the local workflow
- **Quoted-reply fix:** `scripts/main/zalo-bridge/zaloClient.js` installed over upstream npm by `zalo-common.sh` (maps `data.quote.*` for attachment resend)

MIT conditions apply: keep this notice (and the upstream LICENSE text) with distributed copies.
