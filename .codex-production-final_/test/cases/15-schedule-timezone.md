# Case: schedule timezone (daily local time)

Verify that a daily schedule at a fixed **local** clock time uses **today**
when that time is still in the future, not "tomorrow".

## Goal

At `05:58 Asia/Ho_Chi_Minh`, user asks: *every day at 06:00 alert on Zalo*.
Bot must schedule **today 06:00**, not tomorrow.

## Preconditions

- High or Medium with Zalo optional
- `TZ=Asia/Ho_Chi_Minh` on Hermes and host
- Hermes `hermes cron` available

## Steps (unit — no VPS)

1. Run `python test/scripts/schedule_timezone_unit.py`
2. Assert `next_daily_run(6, 0)` at fake now `05:58` → same calendar day
3. Assert at fake now `06:01` → next calendar day

## Steps (lab — Zalo, optional SSH)

1. Note local time in `Asia/Ho_Chi_Minh`
2. Send Zalo DM: set daily alert at **two minutes from now**
3. Confirm reply mentions **today's date** (not tomorrow)
4. Send at `06:01`: set daily `06:00` → confirm **tomorrow** / next day

## Pass criteria

- Unit tests PASS
- User-facing text never includes `job_id:` or cron session names
- No "tomorrow" when target time today is still ahead of now

## Fail events

- Bot says "tomorrow" at 05:58 for 06:00 today → FAIL
- Reply exposes `Cronjob Response` or internal ids → FAIL
