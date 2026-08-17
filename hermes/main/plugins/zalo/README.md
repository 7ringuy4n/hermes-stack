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

## Home channel (cron / cross-platform)

Hermes delivers cron results and cross-platform notices to a **home channel**. If none is set, upstream gateway would prompt every new session with `/sethome`.

| Env | Default | Function |
|-----|---------|----------|
| `ZALO_HOME_CHANNEL` | empty | Manual home: `threadId` or `user:threadId` / `group:threadId` |
| `ZALO_AUTO_SETHOME` | `1` | Silently claim home from the first allowed **DM** (no user-facing prompt) |
| `ZALO_AUTO_SETHOME_DM_ONLY` | `1` | Never auto-claim a group as home |

Disable auto-sethome with `ZALO_AUTO_SETHOME=0` and run `/sethome` once in the desired chat (or set `ZALO_HOME_CHANNEL`).

## Admin commands

| Command | Who | Effect |
|---|---|---|
| `!zalo claim` | anyone (proxy logged in) | First setup / take sole admin when empty or still bridge `ownId` |
| `!zalo admin` | anyone | Show current sole admin |
| `!zalo admin transfer @tag\|uid\|reply` | current admin | Move sole admin to one other user |

Durable file: `zalo_admin_users.txt` under Hermes data (exactly one uid).

## Self-heal

- Adapter: on SSE reconnect loop, drop `Last-Event-ID` and recreate session (no manual restart).
- Host timers: `assistant-stack-watch` (2m) + `assistant-zalo-watch` (1m when `ENABLE_ZALO=1`).
- Default: on `sseClients==0`, restart **bridge only** (`ZALO_WATCH_RESTART_HERMES=0`). Stack-watch does **not** restart Hermes on probe fail (`STACK_WATCH_RESTART_HERMES=0`). Set those env vars to `1` only if you explicitly want the old restart behavior.

## Related

- [architect/social-app/zalo](../../../architect/social-app/zalo/README.md)
- Upstream: https://github.com/cuongdev/hermes-zalo-plugin
