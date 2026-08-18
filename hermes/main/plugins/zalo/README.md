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
| `autosend.py` | Compound file-send window (sequence clock + grace) |
| `multi_request.py` | Compound split vs keep-whole schedule jobs |
| `workflow_client.py` | HTTP client for generic workflow jobs / lịch |
| `inbound_queue.py` | FIFO payload helpers (Valkey or in-memory) |
| `gateway_noise.py` | Drop Hermes busy/interrupt `/busy` copy |
| `gate_valkey.py` | Valkey rate / answering / inbound FIFO |
| `turn_wait.py` | Isolated job sessions + wait-until-idle |
| `ux_copy.py` | Locale pick for `messages/ux.json` (no hardcoded user copy) |
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
| Immediate list (`tin nhắn 1` / `1 …` `2.Sau đó` / one-line `1. … 2. …`) | Split into **durable jobs**. Each instruction is wrapped “chỉ làm đúng việc này”. Autosend keeps files for the **whole sequence**. Send the file/result only — no success ack line. |
| Schedule list (`đặt lịch`, `daily` / `hằng ngày`, weekly / monthly / yearly, or a clock) | Stored as a **schedule**. Clock-only `đặt lịch lúc HH:MM` is **once** (removed after it runs). Named cadence words set daily / weekly / monthly / yearly. At tick time the scheduler creates one job per numbered item. Extra markers: `ZALO_SCHEDULE_KEEP_WHOLE=term1,term2`. |
| Rate limit | Announce once, **enqueue** the message, process later. Copy in `messages/ux.json` `queue.rate_limited`. |
| Queue full | Cap `ZALO_INBOUND_QUEUE_MAX` (default **8** waiting items / thread). `queue.full` line. Valkey down → fail-open sequential turns. Inbound requests only — not a response queue. |
| Hermes busy / `/busy` tips | Dropped on Zalo. Never show “Interrupting current task” or First-time `/busy` copy. |

Cron jobs with `deliver: origin` reply in the **same Zalo thread that created them** (DM if you asked in a DM, group if you asked in a group). `ZALO_HOME_CHANNEL` is only the fallback when origin/home is unset. The workflow service owns execution; `jobs.json` stays for list/CRUD compatibility (`no_agent`).

## Admin commands

| Command | Who | Effect |
|---|---|---|
| `!zalo claim` | anyone (proxy logged in) | First setup / take sole admin when empty or still bridge `ownId` |
| `!zalo admin` | anyone | Show current sole admin |
| `!zalo admin transfer @tag\|uid\|reply` | current admin | Move sole admin to one other user |
| `!zalo schedule list` | current admin | List lịch **in this DM/group** |
| `!zalo schedule list all` | current admin | List **all** user lịch (every DM/group) |
| `!zalo schedule show\|add\|update\|remove` | current admin | CRUD. `--time` / `--timer HH:MM` change the clock. List/show prints `HH:MM`. Index numbers follow the current chat list; `show all 1` / `update all 1` / `remove all 1` use the global list. |

Durable file: `zalo_admin_users.txt` under Hermes data (exactly one uid).

## Self-heal

- Adapter: on SSE reconnect loop, drop `Last-Event-ID` and recreate session (no manual restart).
- Host timers: `assistant-stack-watch` (2m) + `assistant-zalo-watch` (1m when `ENABLE_ZALO=1`).
- Default: on `sseClients==0`, restart **bridge only** (`ZALO_WATCH_RESTART_HERMES=0`). Stack-watch does **not** restart Hermes on probe fail (`STACK_WATCH_RESTART_HERMES=0`). Set those env vars to `1` only if you explicitly want the old restart behavior.

## Related

- [architect/social-app/zalo](../../../architect/social-app/zalo/README.md)
- Upstream: https://github.com/cuongdev/hermes-zalo-plugin
