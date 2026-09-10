# Case: daily schedule of one weather + fuel infographic

Same **one-task** poster as case 26, wrapped as a recurring schedule. Classify
must store **one** instruction (the poster), not three jobs (draw / fuel / weather).

**Architect:** Secret Probe → LLM classify (`task_hint=schedule`, `cadence=daily`,
one instruction) → Schedule skill → Go worker. Tick injects the poster text;
Hermes creates **one** job.

## Fixture

```text
hằng ngày lúc 07:00 GMT+7:
Vẽ hình Thành phố Hồ Chí Minh dựa trên tình hình thời tiết thực tế hiện tại, trên hình thể hiện ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất và thông tin tình hình thời tiết hiện tại, bằng tiếng Việt.
```

English twin:

```text
every day at 07:00 GMT+7:
Draw an image of Ho Chi Minh City based on the actual current weather. On the image, briefly show the latest E5 RON92 and E10 RON95 gasoline prices and the current weather, in Vietnamese.
```

Do not mix languages in one run. Origin = admin DM only.

## Contrast

| Case | User shape | Jobs at tick |
|------|------------|--------------|
| 16 | Two labeled tasks (image, then fuel text) | 2 |
| 25 | Four numbered tasks (hello, image, fuel, video) | 4 |
| 26 | One poster sentence, now | 1 (immediate) |
| 27 | One poster sentence, daily cron | 1 per fire |

## Steps (unit)

```bash
python test/scripts/llm_classify_unit.py
python test/scripts/workflow_unit.py
python test/scripts/multi_request_unit.py
```

Daily fixture stays **one** schedule payload (`split_compound_requests` length 1).
`plan_instructions` length 1. Mock cron `0 7 * * *`.

## Steps (lab)

Case 26 lab also classifies this daily wrapper (`PLAN_HINT schedule PLAN_N 1`).
A full fire is optional (`ZALO_INFOGRAPHIC_DAILY=1` on `zalo_weather_fuel_lab.py`).

## Pass criteria

- Units PASS
- `task_hint=schedule`, `PLAN_N 1`, cron `0 7 * * *` (07:00 GMT+7)
- Must not explode into weather + fuel + overlay jobs
- Optional fire: one `send-attachment` to the admin DM

## Fail events

- Daily wrapper classified as `tool` with no cron → FAIL
- `PLAN_N` ≥ 2 → FAIL
- Numbered-list explode (case 25 behavior) → FAIL
