# Case: Zalo Tn — Đà Nẵng weather on image with live metrics

## Goal

Search current Đà Nẵng weather, deliver scenic image with bottom-left overlay that
includes live metrics (temperature and/or wind), not title+timestamp alone.
Agent must OCR/rate the artifact (AGENT_RULES §29.2).

## Script

`test/scripts/zalo_tn_weather_danang_inject.py`

## Pass

- New/rewritten weather-scene image after inject
- OCR shows metric lines (Nhiệt độ / °C and preferably Gió)
- No placeholder / SFW / typo tokens
- Soft-skip only on genuine Omni quota/provider failure
