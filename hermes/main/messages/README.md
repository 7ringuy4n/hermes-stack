# hermes / messages

## Purpose

**Editable** user-facing and admin-facing copy so operators can improve UX without patching adapter code.

## Files

| File | Function |
|---|---|
| `learn-notify.json` | Knowledge pending/approved/deleted notify templates (`from={id}|{name}`) |
| `ux.json` | Cite empty/ingest-down, secret-probe refuse, Zalo queue/rate-limit lines |

### `ux.json` → `queue` (Zalo inbound FIFO)

| Key | Default text | Override env | When |
|-----|----------------|--------------|------|
| `rate_limited` | Bạn gửi hơi nhanh — tin này đã vào hàng chờ… | `ZALO_RATE_LIMIT_MSG` | Rate window exceeded; message **is queued** (announced once per window) |
| `queued` | Mình đang trả lời tin trước… | — | Reserved (compound follow-up copy) |
| `full` | Hàng chờ đầy. Gửi lại sau giúp mình. | `ZALO_QUEUE_FULL_MSG` | Valkey queue at cap — message **not** enqueued |

Capacity: `ZALO_INBOUND_QUEUE_MAX` default **3** waiting items per thread (`inbound_queue.py`). TTL default **3600** s (`ZALO_INBOUND_QUEUE_TTL_S`). This queue is **inbound requests only** (compound parts + rate-limit defer). Outbound replies are sent as each Hermes turn finishes — there is no separate response FIFO. Same defaults on Low / Medium / High when `ENABLE_ZALO=1`.

## Rules

- UTF-8 always (Vietnamese supported)
- Services/skills load by path/env (e.g. `LEARN_NOTIFY_PATH`)
- Do not embed long paragraphs in Python adapters

## Related

- [skills](../skills/README.md)  
- [architect/notification](../../architect/notification/README.md)
