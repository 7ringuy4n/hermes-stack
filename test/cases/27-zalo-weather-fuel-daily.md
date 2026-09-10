# Case: daily schedule of one weather + fuel infographic

Same **one-deliverable** image as case 26, wrapped as a schedule. Classification
must preserve the complete inner dependency graph in one stored schedule: one
focused search per evidence domain, then exactly one composed-image task that
depends on every search. The wrapper must not execute or flatten the graph.

**Architect:** Secret Probe → LLM classify (`task_hint=schedule`,
`schedule_delivery=process`) → Schedule skill → Go worker. A due tick injects
the stored plan; the Zalo adapter executes its host-owned search/composition
path and delivers exactly one image.

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

Run the immediate image gate and the two-minute full-fire gate:

```bash
python test/scripts/zalo_weather_fuel_lab.py
python test/scripts/zalo_scheduled_composed_image_lab.py
```

The full-fire fixture uses the same inner work with `once_after=120`. It resolves
the destination from runtime state, records no numeric identity, and requires
the schedule-created synthetic message id to correlate to exactly one
bridge-acknowledged image delivery.

## Pass criteria

- Units PASS
- `task_hint=schedule`, `schedule_delivery=process`, cron `0 7 * * *` for the
  recurring fixture or `delay_seconds=120` for the release gate
- Two or more independently focused search details followed by exactly one
  media detail whose dependency list contains every search index
- At fire, the queue-enabled adapter executes the persisted plan before generic
  Hermes fallback
- Exactly one source-correlated, bridge-acknowledged image is delivered
- No structured-plan truncation and no quote attempt against the synthetic
  schedule event

## Fail events

- Daily wrapper classified as `tool` with no cron → FAIL
- Stored plan is missing, flattened, or reclassified at fire → FAIL
- Text answer instead of an image → FAIL
- Synthetic quote rejection, missing source correlation, duplicate image, or
  planner truncation → FAIL
