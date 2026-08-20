# Case: once-schedule with numbered tasks must not hit knowledge-cite

A one-shot Zalo schedule whose numbered items include “không trích dẫn nguồn”
must become a **schedule**, not a knowledge-catalog refuse.

**Architect:** Secret Probe → LLM classify (`task_hint=schedule`, `cadence=once`,
three `instructions[]`) → Schedule skill → Go schedule worker. Knowledge-cite
intercept must not run. Tick injects inner work; Hermes creates **one job per
numbered item**.

## Fixture

```text
đặt lịch chạy một lần lúc 11:24
1. Gửi một tin nhắn chào buổi sáng đến mọi người.
2. Tóm tắt ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất không trích dẫn nguồn
3. Tóm tắt ngắn gọn thông tin tình hình thời tiết Hồ Chí Minh hiện tại
```

Do not mix with case 14 (internal docs cite) or case 27 (one overlay poster).

## Why it failed

- Adapter cite intercept treated substring `trích dẫn` as a catalog lookup, so
  ingest answered `Không thấy kiến thức khớp «…»` and Hermes never classified.
- A nearby once-lịch stored **one** paraphrased English instruction
  (“Schedule a one-time task…”) and cron `25 11 * * *`, so tick ran 1 meta-job
  instead of the three user tasks.

## Fix (source)

- Cite intercept is LLM classify `task_hint=knowledge` only. Numbered once-lịch is `schedule` + `PLAN_N 3`. Classify prompt: wrapper sets cron only; keep the user’s language; clock is exact.

## Preconditions

- `ENABLE_ZALO=1` for lab
- Origin = admin DM only (`zalo_admin_users.txt`), `thread_type=user`

## Steps (unit — no VPS)

```bash
python test/scripts/knowledge_cite_unit.py
python test/scripts/llm_classify_unit.py
python test/scripts/multi_request_unit.py
```

## Steps (lab — optional)

1. Send the fixture as **one** Zalo bubble (use a clock **two minutes from now**
   if 11:24 has passed). Expect one lịch confirm, **not** the cite empty-hit line.
2. When it fires: three jobs — greeting, fuel summary, HCMC weather summary.
3. Deliveries stay in the admin DM.

## Pass criteria

- Unit PASS
- Classify: `task_hint=schedule`, `cadence=once`, `PLAN_N 3`, cron matches the
  stated clock
- No `Không thấy kiến thức khớp`
- Tick: 3 COMPLETED jobs, not one wrapper sentence

## Fail events

- Cite refuse on ingest → FAIL
- `PLAN_N 1` or English “Schedule a one-time task…” instruction → FAIL
- Cron rounded to another minute → FAIL
- Jobs sent to a group instead of admin DM → FAIL
