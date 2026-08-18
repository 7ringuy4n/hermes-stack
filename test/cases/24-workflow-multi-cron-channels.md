# Case: plenty-in-one-message + same-time vs different-time cron (Zalo and Hermes)

One inbound message can hold many tasks. A lịch/schedule with many numbered
items must create **one job per item** at tick time. Two schedules at the
**same clock** must both fire without mixing users. Two schedules at
**different clocks** must fire independently. This applies to **Zalo users**
and **direct Hermes API users**.

## Fixtures

**Immediate plenty (6 items, no daily wording):**

```text
Thực hiện:
1. Gửi tin chào buổi sáng
2. Vẽ hình thời tiết HCMC
3. Cập nhật giá xăng E5 RON92 và E10 RON95
4. Báo tỷ giá USD/VND
5. Tóm tắt lịch hôm nay
6. Nhắc uống nước
```

**Daily plenty at 13:54 GMT+7 (keep whole on ingest):**

```text
hằng ngày lúc 13:54 GMT+7:
1. Send daily wakeup in DM/group: * a 6:00 AM GMT +7
2. Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế
3. Cập nhật giá xăng E5 RON92 và E10 RON95
4. Báo tỷ giá USD/VND
5. Tóm tắt lịch hôm nay
6. Nhắc uống nước
```

The body may still mention `6:00 AM`. The schedule clock must stay **13:54**.

## Why 13:54 GMT+7 missed a run

Creating or updating a daily clock **in the same minute** used to set
`next_run_at` to **tomorrow** (`candidate <= now` → +1 day). Example: save
`13:54` at `13:54:20` → no fire today, no Zalo/Hermes reply.

Fix: 120s grace keeps that run **due today** so the ticker catch-up fires.
After a successful fire, `next_run_at` advances to the next calendar day.

## Steps (unit — no VPS)

```bash
python test/scripts/workflow_schedule_concurrency_unit.py
python test/scripts/workflow_unit.py
python test/scripts/workflow_gateway_unit.py
python test/scripts/workflow_turn_wait_unit.py
python test/scripts/multi_request_unit.py
```

Run as **separate** processes.

## Steps (VPS — record_only, no user-facing send)

```bash
python test/scripts/workflow_vps.py
```

## Steps (lab — Zalo phone)

1. Send the immediate 6-item list as **one** Zalo bubble. Expect all 6 intents, no success-ack line, no `/busy` tip.
2. Send the 13:54 (or **two minutes from now**) daily list. Expect **one** lịch confirm.
3. When it fires: all 6 items, origin thread, no `/busy`.
4. From a second Zalo user (or second thread), save another lịch at the **same** clock. Both must run; replies must not mix threads.

## Steps (lab — Hermes API)

Authenticated `POST /v1/chat/completions` with the same fixtures. Immediate list → workflow jobs. Schedule-shaped text → stored schedule. Same-clock vs different-clock behaviour matches the unit script.

## Pass criteria

- Units PASS
- Same clock: Zalo `execute=hermes` and Hermes `execute=hermes_http` both create 6 jobs, no shared job ids
- Different clock: 06:00 tick does not fire 12:00
- 13:54 created at 13:54:20 still fires **today**
- Clock extract prefers `lúc 13:54` over a `6:00` inside item 1
- Each Zalo `execute=hermes` job uses an isolated Hermes session and may run in parallel (cap `ZALO_WORKFLOW_PARALLEL`). Replies are not merged into one pending follow-up.

## Fail events

- Only the first numbered item runs → FAIL
- Four jobs complete in ~8s each while the agent is still running → FAIL (worker did not wait for the turn)
- Same-minute create skips to tomorrow → FAIL
- Two users at 13:54 share one workflow / mix replies → FAIL
- 12:00 job runs at the 06:00 tick → FAIL
- Interrupt / First-time `/busy` on Zalo → FAIL
