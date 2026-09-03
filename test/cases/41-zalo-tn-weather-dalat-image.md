# Case: Zalo Tn — Da Lat weather + eye-catching image (OCR eval)

## Goal

Live weather lookup for Da Lat then deliver a scenic weather-scene image with
host overlay facts. Agent must OCR/rate the artifact (AGENT_RULES §29.2), not
assert inject HTTP alone.

## Script

`test/scripts/zalo_tn_weather_dalat_inject.py`

## Pass

- New image under `media/out` after inject
- No Hermes `shutdown_watchdog` / exit 75 during the turn
- OCR shows place/title and/or temperature without placeholders / SFW / typos
- Soft-skip (`SKIP_QUOTA` / `PASS_PARTIAL_QUOTA`) only when Omni queue/quota blocks hops
