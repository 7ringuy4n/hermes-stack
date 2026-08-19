# Case: Zalo weather + fuel infographic (one user request)

A **single** inbound-style request: draw one Ho Chi Minh City image from **live
weather**, and **on that same image** show short Vietnamese overlays for the
latest **E5 RON92 / E10 RON95** prices and current weather. Not four numbered
jobs (that is case 25). Not “image then a separate fuel text” (that is case 16).

**Architect:** Secret Probe → LLM classify (`task_hint` + one `instructions[]`
item) → one Hermes turn or one workflow job → file under `media/out` → Zalo
`send-attachment` to the **admin DM**.

## Fixture (Vietnamese — lab default)

```text
Vẽ hình Thành phố Hồ Chí Minh dựa trên tình hình thời tiết thực tế hiện tại, trên hình thể hiện ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất và thông tin tình hình thời tiết hiện tại, bằng tiếng Việt.
```

English twin (same one-task meaning; do not mix languages in one lab run):

```text
Draw an image of Ho Chi Minh City based on the actual current weather. On the image, briefly show the latest E5 RON92 and E10 RON95 gasoline prices and the current weather, in Vietnamese.
```

Origin = current Zalo admin DM only (`zalo_admin_users.txt`, `thread_type=user`).

## Why this is special

- Real user phrasing: one sentence, several facts, **one picture**.
- Classify must keep `instructions` length **1** (`task_hint` typically `tool`).
- Image-gen may be off; dispatcher / skills must still attempt the poster.
- Pass requires the **file sent** to the admin DM, not only written to disk.

## Steps (unit — no VPS)

```bash
python test/scripts/llm_classify_unit.py
python test/scripts/workflow_unit.py
python test/scripts/multi_request_unit.py
python test/scripts/autosend_unit.py
```

Mock classify for the Vietnamese fixture has `instructions` length 1.

## Steps (lab — current Zalo login)

```bash
python test/scripts/zalo_weather_fuel_lab.py
```

1. Plugin `loggedIn`, SSE owner, admin DM origin.
2. Live `POST /v1/classify` on the Vietnamese fixture: `PLAN_N 1`, not `schedule`.
3. `POST /v1/workflows` with that one instruction (origin admin DM, `test=case26`).
4. Watch until the job completes and Hermes prints `send-attachment path`.

## Pass criteria

- Units PASS
- Classify `PLAN_N 1` (must not explode weather / fuel / overlay into 2–3 jobs)
- One `[zalo] workflow job done`
- At least one `send-attachment` to the **admin DM**
- Image should carry **on-image** weather + E5/E10 overlay (dispatcher `overlay` lines), not a blank scene plus a separate caption only
- No `/busy` tip; no group / non-admin thread
- No `SECRET` task_hint

## Fail events

- `PLAN_N` ≥ 2 for this fixture → FAIL (split overlay facts)
- Job COMPLETED with a file in `media/out` but no `send-attachment` → FAIL
- A leftover isolated job from case 25 sends this infographic (`zalo_send_file` on a previous `::job::` id) → FAIL
- Only a text caption describing the image, no file → FAIL
- Replies to a group → FAIL
