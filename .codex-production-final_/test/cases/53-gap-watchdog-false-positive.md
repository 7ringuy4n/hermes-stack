# Case 53: Watchdog False Positive

**Gap matrix id:** Case 49 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Ensure the watchdog never restarts a healthy worker because another subsystem is busy.

This directly targets the recent dispatcher flap incident where the watchdog restarted dispatcher while OCR/media jobs were running.

## Procedure

Run long:

- OCR;
- media extraction;
- Whisper;
- image generation;
- workflow jobs.

During processing:

- delay health response;
- increase CPU;
- increase queue depth;
- temporarily delay dependency response.

## Pass criteria

- Healthy worker is not restarted.
- In-flight job survives.
- RestartCount remains unchanged when service is actually healthy.
- Disabled components are not probed/restarted.

---
