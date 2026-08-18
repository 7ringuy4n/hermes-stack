# Case: plenty of requests in one Zalo message (Valkey queue)

One inbound bubble can hold several tasks. They must all run, in order, without
Hermes busy-interrupt UX. Rate-limited follow-ups are queued, not dropped.

## Fixtures

**Daily job (one cron, one queue item):**

```text
1. Send daily message to wakeup every in DM/group: * a 6:00 AM GMT +7
2. Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế
3. Cập nhật ngắn gọn nội dung giá xăng E5 RON92 và E10 RON95 gần nhất
```

This stays **one** schedule payload (wakeup + image + prices every 06:00 `Asia/Ho_Chi_Minh`).

**Immediate list (three queue items):** same three tasks **without** daily/wakeup wording.
Valkey FIFO runs them one after another on that thread.

## Behaviour

| Signal | Result |
|--------|--------|
| Compound inbound | Enqueue on Valkey (`assistant:gate:q:<thread>`). Drain one turn at a time. |
| Rate limit | Tell the user once, **keep** the message in the queue, process later. |
| Queue full | Configurable `queue.full` line. Default cap **3** (`ZALO_INBOUND_QUEUE_MAX`). |
| Valkey down | Fail-open: in-process sequential turns (no drop). |

Disable with `ZALO_INBOUND_QUEUE=0`. Copy: `hermes/main/messages/ux.json` → `queue.*` (env `ZALO_RATE_LIMIT_MSG` / `ZALO_QUEUE_FULL_MSG` override).

## Steps (unit — no VPS)

1. `python test/scripts/inbound_queue_unit.py`
2. `python test/scripts/multi_request_unit.py` (schedule keep-whole still PASS)

Run as **separate** processes.

## Steps (lab)

1. Send the **daily** fixture once. Expect one schedule confirm. No `/busy` tip.
2. Send the **immediate** 3-item list. Expect wakeup-style text **and** image attempt **and** fuel blurb, in order.
3. Burst two short pings inside the rate window. Expect the rate-limit queued line, then **both** answers (not a drop).

## Pass criteria

- Units PASS
- All numbered intents addressed
- No interrupt / First-time `/busy` on Zalo
- Simple one-line chat still aims **≤ 5s** on host (case 17)

## Fail events

- Only item 1 runs → FAIL
- Rate-limit **drops** the extra message with no later answer → FAIL
- Interrupt tip delivered → FAIL
