# Case: Zalo media generation + lịch delivery (video send, leftover claim, quiet)

Regression lab for **media generation** and **schedule / cron ticks**. Complements case 25 (four numbered jobs) and case 26 (one infographic). Focus: the file that landed must be **sent** to the admin DM; a leftover isolated job must not steal the next run’s media; video must be a Zalo-acceptable H.264 clip; mid-generation chatter must not reach the user.

## Why this exists

Production failures seen on High + Zalo:

1. Video written under `media/out` but `/send-attachment` returned Zalo **invalid parameter** (`Tham số không hợp lệ`) — matplotlib/odd codec mp4.
2. Isolated job stayed `idle=False` and a **late autosend** after `workflow job done` claimed a **later** job’s jpg.
3. Hermes invented matplotlib/manim instead of dispatcher `POST /v1/image` and `POST /v1/video`.
4. Users received process narration while the file was still rendering.

## Fixture

Reuse case 25 English four-item lịch **or** run after case 25/26 on the same host. Origin = current Zalo admin DM only.

Default video path in source: dispatcher **`POST /v1/video`** (still → ffmpeg H.264). Images: **`POST /v1/image`** with optional `overlay` fact lines. Medium/High first-setup must leave `IMAGE_BACKENDS` non-empty (`llm,vendor,comfy-cpu,comfy-gpu`).

## Steps (unit — no VPS)

```bash
python test/scripts/autosend_unit.py
python test/scripts/overlay_unit.py
python test/scripts/gateway_noise_unit.py
python test/scripts/workflow_turn_wait_unit.py
```

- `file_in_send_window` rejects mtime **after** an isolated job’s ceiling.
- Overlay paints caller-supplied lines (no NLU).
- Process narration (matplotlib / “let me generate”) is dropped; fuel prices are kept.

## Steps (lab — current Zalo login)

```bash
python test/scripts/zalo_special_four_lab.py
python test/scripts/zalo_weather_fuel_lab.py
```

1. Case 25: after fire, `media/out` has a **new** `.mp4` whose mtime is in the fire window **and** Hermes prints `send-attachment path …mp4` (not only a leftover file from an earlier hour).
2. Case 26: one `send-attachment` for the infographic; that path must belong to the case 26 job, not `::job::` of an earlier leftover video job.
3. Hermes logs in the fire window must not show `send-attachment fail` for the new mp4 after remux.
4. No `/busy` tip. No group thread.

## Pass criteria

- Units PASS
- New video in the fire window is **sent** (`send-attachment` … `.mp4`)
- Case 26 `attach>=1` on the admin DM
- `IMAGE_BACKENDS` non-empty on High (dispatcher `/health` lists backends)
- Isolated job after `workflow job done` does not send a file written **after** its ceiling

## Fail events

- mp4 on disk, no `send-attachment` for that mp4 → FAIL
- `send-attachment fail` / invalid parameter and no remux retry success → FAIL
- Leftover job `zalo_send_file` of a later infographic → FAIL
- Job COMPLETED in a few seconds while the agent is still writing media → FAIL
- Process narration (“Rendering frames”, “let me generate”) reaches Zalo → FAIL
