# Case: Bare photo always replies; Router rotates free Omni models

## Goal

1. A bare Zalo image with OCR text must produce a **deterministic Zalo reply**
   containing the OCR excerpt — never silence when PaddleOCR succeeded.
2. Router Worker must **rotate** the Omni chat combo (free members) with a longer
   timeout, then try `OMNIROUTER_FAILOVER_MODELS` (default `auto/best-free`) when
   a hop returns subscription/403 or empty chat JSON.

## Steps

1. Local: `python test/scripts/omni_rotate_noreply_unit.py`
2. Local: `python test/scripts/model_router_chat_norm.py`
3. Lab: rebuild `router-worker`; confirm env
   `MODEL_ROUTER_TIMEOUT_S=180`, `OMNIROUTER_ROTATE_ATTEMPTS=3`,
   `OMNIROUTER_FAILOVER_MODELS=auto/best-free`
4. Send **two** bare photos back-to-back → each gets an OCR ack (second must not
   be silent). Glyph-noise OCR should empty-ack, not dump single letters.
5. `POST /v1/chat/completions` with `stream:true` still returns content when the
   first Omni member is slow/blocked (router logs `[route] failover ...`)

## Pass criteria

- Units print `PASS`
- Bare image + OCR never ends with zero bot messages
- Router does not stream a raw subscription 403 through to Hermes
