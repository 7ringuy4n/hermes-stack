# Case: Zalo busy interrupt + multi-task cron

Hermes must not show busy/interrupt UX on Zalo. A scheduled job with several
numbered tasks must run **all** of them.

## Issue

1. User must never see:

```text
⚡ Interrupting current task. I'll respond to your message shortly.
💡 First-time tip — … `/busy queue` … `/busy steer` … `/busy status` …
```

2. A cron payload like:

```text
1. send daily message to wakeup every in DM/group: *
2. vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế
3. Cập nhật giá xăng E5 RON92 và E10 RON95
```

must execute **wakeup + image + fuel prices** on each run — not only the first line.

## Why it failed

- Upstream Hermes injects the interrupt tip when a new turn starts while another is still running.
- Sequential compound `handle_message` without waiting, or **several crons at the same clock**, triggered that UX.
- One unsplit turn plus media-out “stop after the file” dropped later cron items.

## Fix (source)

- Adapter drops busy/interrupt `/busy` copy (`gateway_noise.py`).
- Immediate compound still splits, but waits until the current part has sent before the next.
- Schedule-shaped lists stay **one job** (`ZALO_SCHEDULE_KEEP_WHOLE`, default on). Markers include `hằng ngày` / `hàng ngày` / `GMT+7`.
- Skills: one cron, complete every numbered item after media.

## Preconditions

- `ENABLE_ZALO=1` for lab
- Unit scripts need no VPS

## Steps (unit — no VPS)

1. `python test/scripts/gateway_noise_unit.py`
2. `python test/scripts/multi_request_unit.py` — schedule fixture stays **one** part; immediate `1`/`2.Sau đó` still splits
3. `python test/scripts/workflow_schedule_concurrency_unit.py` — plenty (6) items, same-time vs different-time, Zalo + Hermes, 13:54 GMT+7 catch-up

## Steps (lab — optional)

1. Send the three-item daily list as **one** Zalo message to **create** the schedule. Expect one confirmation, **no** interrupt tip.
2. When the job fires (or a short test cron): expect wakeup text **and** weather image **and** fuel prices.
3. Send an immediate compound (`tin nhắn 1` image, `tin nhắn 2` prices) while idle: both run, **no** `/busy` tip.

## Pass criteria

- Unit PASS
- Lab: no interrupt / First-time `/busy` text on Zalo
- Lab: cron run addresses all three intents
- SSE stays at 1

## Fail events

- Interrupt or `/busy` tip delivered to Zalo → FAIL
- Cron run only does item 1 (image or wakeup) and skips fuel → FAIL
- Three parallel crons at the same HH:MM created from one list → FAIL
