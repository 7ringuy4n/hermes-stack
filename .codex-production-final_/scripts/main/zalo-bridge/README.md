# Zalo bridge overlays (assistant-stack SoT)

Upstream npm package [`hermes-zalo-plugin`](https://github.com/cuongdev/hermes-zalo-plugin) (MIT, Cường Tuấn Nguyễn) is installed globally on the host. This directory holds **durable** bridge file overrides applied by `zalo-common.sh` after `npm install -g hermes-zalo-plugin`.

| File | Why |
|---|---|
| `zaloClient.js` | Fixes quoted-reply SSE payload: `quote` must map `data.quote.*`, not the current message (`data.content` / `data.msgId`). Without this, Hermes cannot resolve “gửi lại file trong tin nhắn” from quoted attachments. |
| `markdownToZalo.js` | Required local import for overlay `zaloClient.js` (upstream main); **not** shipped in npm `hermes-zalo-plugin@1.0.x`. Omitting it crash-loops the bridge (`ERR_MODULE_NOT_FOUND`). |

Applied by `zalo_install_bridge_overlays()` — copies the full bundle, then `node --check` + local-import verify before bridge restart. Not runtime regex patches in `patch_zalo_bridge_inject.py`.
