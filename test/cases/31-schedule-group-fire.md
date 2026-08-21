# Case: Schedule fire into named Zalo group

## Goal

DM creates a schedule that delivers into a named group (e.g. LC group). When due, the fire is processed in that group even if `ZALO_GROUP_MODE=mention` (no @bot required for `scheduleFire`).

## Preconditions

- Schedule Worker active; Zalo logged in; group known in channel registry (`!zalo refresh` / inbound)
- Media/OCR optional for inner work

## Steps

1. From admin DM: `đặt lịch chạy một lần lúc HH:MM vào group Zalo LC group và …` (inner work: short hello)
2. Expect immediate ack with schedule id + next run (not “send inside the group”)
3. Wait until fire (or `POST schedule-worker /v1/schedules/tick` in lab)
4. Expect reply **in the group**, not dropped by mention-gate
5. `GET /v1/schedules/history?thread_id=<group_id>` shows status `ok` or `error` with detail

## Pass criteria

- Create path: classify → Schedule Worker store → ack (no Hermes free-chat inventing chat IDs)
- Fire path: inject `scheduleFire=true` bypasses mention / rate / inflight drops
- History API returns the fire row
- Concurrent user chat in same thread does not permanently block scheduleFire

## Fail events

- Fire logged `fired zalo` but no Hermes turn in group (mention drop)
- Create hangs on classify `classifier` 401 without falling back to chat combo
- CRITICAL Dispatcher DOWN spam on brief restarts (streak &lt; HEALTH_FAIL_STREAK)

## Lab

```bash
python test/scripts/schedule_group_fire_lab.py
```
