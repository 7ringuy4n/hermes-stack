# Case 40 — Zalo Tn: weather PPTX + weather-on-image bottom-left overlay

## Goal

Verify live weather PPTX create and city photo with compact Vietnamese overlay
(bottom-left) without placeholders, SFW leakage, or misspelled labels.

## Steps

1. Inject as the authorized `ZALO_TEST_USER_ID` via `test/scripts/zalo_tn_weather_overlay_pptx_inject.py`.
2. Message A: create PPTX with current Vung Tau weather facts.
3. Message B: update HCM weather and write facts on HCM photo at bottom-left.

## Pass

- Newest `.pptx` under media/out contains filled weather facts (not empty topic-only).
- Newest weather image has Pillow overlay (real values); no `<value after search>`, no `SAFE-FOR-WORK` on image, Vietnamese labels spelled correctly (`Nhiệt độ`, `Thời tiết`).
- Zalo Tn receives the file/image.

## Fail

- Empty/trivial PPTX or remapped PDF with only a topic line.
- Diffusion-burned board with placeholders/typos/SFW header.
- Silent turn or credential/backend chatter after delivery.

## Skip

Free-model / Omni quota or rate-limit (`maxWaitMs`) failures — soft-skip and retest later.
