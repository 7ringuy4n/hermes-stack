# hermes / plugins / zalo

Hermes-side Zalo adapter for the assistant stack.

## Attribution (required)

| | |
|---|---|
| **Original** | [hermes-zalo-plugin](https://github.com/cuongdev/hermes-zalo-plugin) |
| **Author** | **Cường Tuấn Nguyễn** ([cuongdev](https://github.com/cuongdev)) |
| **License** | MIT — see [LICENSE](./LICENSE) and [ATTRIBUTION.md](./ATTRIBUTION.md) |

This tree **reuses** that work (via assistant) and **optimizes** it for assistant profiles: mention-before-gates, Valkey helpers, compose `zalo-proxy`, install-after-ready, and a **manual** QR login step.

## Files

| File | Role |
|---|---|
| `adapter.py` | Inbound/outbound handling |
| `gate_valkey.py` | Valkey helpers for rate / already-answering gates |
| `plugin.yaml` | Plugin manifest (`author: cuong` upstream) |
| `ATTRIBUTION.md` | Copyright / reuse notice |

## Attach order

1. Profile stack healthy (`bash run.sh check-medium` / `check-high`)
2. `ENABLE_ZALO=1 bash scripts/main/setup-zalo.sh` — install only (no QR)
3. **You:** `bash scripts/main/login-zalo.sh` — QR / re-login

## Admin commands

| Command | Who | Effect |
|---|---|---|
| `!zalo claim` | anyone (proxy logged in) | First setup / take sole admin when empty or still bridge `ownId` |
| `!zalo admin` | anyone | Show current sole admin |
| `!zalo admin transfer @tag\|uid\|reply` | current admin | Move sole admin to one other user |

Durable file: `zalo_admin_users.txt` under Hermes data (exactly one uid).

## Self-heal

- Adapter: on SSE reconnect loop, drop `Last-Event-ID` and recreate session (no manual restart).
- Host timers: `assistant-stack-watch` (2m) + `assistant-zalo-watch` (1m when `ENABLE_ZALO=1`) restart down containers / hermes when `sseClients==0`.

## Related

- [architect/social-app/zalo](../../../architect/social-app/zalo/README.md)
- Upstream: https://github.com/cuongdev/hermes-zalo-plugin
