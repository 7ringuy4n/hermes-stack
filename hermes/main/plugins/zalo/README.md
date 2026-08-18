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
| `multi_request.py` | Compound split vs keep-whole schedule jobs |
| `inbound_queue.py` | FIFO payload helpers (Valkey or in-memory) |
| `gateway_noise.py` | Drop Hermes busy/interrupt `/busy` copy |
| `gate_valkey.py` | Valkey rate / answering / inbound FIFO |
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

## Compound messages and cron

| Kind | What happens |
|------|----------------|
| Immediate list (`tin nhắn 1` / `1 …` `2.Sau đó`) | Split into turns. **Valkey FIFO** per thread. **`Đã xong.` / `Done.` only after the last part** (e.g. image → prices → ack). |
| Daily / cron list (`daily`, `wakeup`, `hàng ngày`, …) | **Not** split. One Hermes job (one queue item); when it fires, every numbered item must run. Extra markers: `ZALO_SCHEDULE_KEEP_WHOLE=term1,term2`. Set `0` to always split. |
| Rate limit | Announce once, **enqueue** the message, process later. Copy in `messages/ux.json` `queue.rate_limited`. |
| Queue full | Cap `ZALO_INBOUND_QUEUE_MAX` (default **3** waiting items / thread). `queue.full` line. Valkey down → fail-open sequential turns. Inbound requests only — not a response queue. |
| Hermes busy / `/busy` tips | Dropped on Zalo. Never show “Interrupting current task” or First-time `/busy` copy. |

Cron delivery still uses the home channel above. Register **one** job per clock — several crons at the same HH:MM interrupt each other and skip later tasks.

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
