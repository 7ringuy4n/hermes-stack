# Case: Bare attachments always reply; Router rotates free Omni models

## Goal

1. A bare Zalo **image** with vision-ocr text must produce a **deterministic Zalo reply**
   containing the extract or scene summary — never silence when vision read succeeded.
2. A bare Zalo **file** (txt/csv/xlsx/mp3/mp4/…) must produce a **deterministic
   extract ack** after ingest/vision/media-text — never depend on the agent when
   Omni returns capacity-busy 503.
3. Router Worker must **rotate** the Omni chat combo (free members) with backoff
   on capacity-busy, then try `OMNIROUTER_FAILOVER_MODELS` (default
   `auto/best-free`) when a hop returns subscription/403/busy or empty chat JSON.

## Steps

1. Local: `python test/scripts/omni_rotate_noreply_unit.py`
2. Local: `python test/scripts/model_router_chat_norm.py`
3. Local: `python test/scripts/zalo_attachment_unit.py`
4. Lab: rebuild `router-worker` + `hermes`; confirm env
   `MODEL_ROUTER_TIMEOUT_S=180`, `OMNIROUTER_ROTATE_ATTEMPTS=5`,
   `OMNIROUTER_BUSY_BACKOFF_S=3`, `OMNIROUTER_FAILOVER_MODELS=auto/best-free`
5. Send bare photo + csv/xlsx/txt/mp3/mp4 → each gets an extract/vision ack (not only
   Knowledge-pending). Empty vision read should empty-ack.
6. `POST /v1/chat/completions` with `stream:true` still returns content when the
   first Omni member is slow/blocked (router logs `[route] failover ...`)

## Pass criteria

- Units print `PASS`
- Bare attachment extract never ends with zero bot messages (agent optional)
- Router does not stream a raw subscription 403 / capacity-busy through to Hermes
