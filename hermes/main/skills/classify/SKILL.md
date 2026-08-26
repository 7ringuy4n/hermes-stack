---
name: classify
description: "Classify every inbound Zalo (and host) user message into structured purpose JSON. Prompt SoT is this skill's parts, assembled into one system hop. Never reply to the user."
---

# Classify (Zalo inbound purpose)

**Source of truth:** `hermes/main/skills/classify/`  
Envelope: `classify.json` (`timeout_s`, `user_template`, `parts[]`).  
Policy text: `parts/core.txt`, `schedule.txt`, `media.txt`, `delivery.txt`, `schema.txt`.  
Do **not** hand-edit `architect/models/model-router/config/classify.json`.

Router-worker **assembles parts into one `system` string** and makes **one** `POST /v1/classify` LLM call. Do not add a second classify hop.

## When it runs

On **every new Zalo user message** (and gateway/host classify hops), the host must:

1. Strip Valkey `[Prior conversation]` wrappers for the classify input.
2. Call model-router `POST /v1/classify` (combo `classifier` / `MODEL_ROUTER_CLASSIFY_MODEL`).
3. Consume the structured JSON only (`task_hint`, `task_type`, `skill`, `skill_action`, `instructions`, `output_type`, `clock_hm`, `poster_*`, schedule fields, `target_channel`, `tasks[]`, …).
4. Route via `core/worker-routing` / Zalo adapter — **never** re-parse Vietnamese prose with regex dictionaries.

Classify **never** sends a user-facing chat reply. It only structures work.

## Prompt contract

Edit the matching **part** (decision tests, not synonym dictionaries). Illustrations are families; paraphrases must still map.

`user_template` may include Thread / Attachments / Quoted facts supplied by the host — not host NLU.

## Sync (bake fallback)

Runtime: `/opt/data/skills/classify/` (json + `parts/`).  
Image bake ships an **assembled** `config/classify.json` (`system` filled):

```bash
bash scripts/main/sync-model-router-skills.sh
```

## Must follow

1. One SoT folder — this skill. One LLM hop.
2. Host validates enums / protocol only; no keyword NLU for intent. Classify Python does not phrase-scan schedule, delay, or destination.
3. List/inspect ≠ delete; create schedules need temporal fields; destination names go in `target_channel`.
4. After editing a part, sync the bake fallback and recreate `router-worker`.

## Related

- `core/worker-routing` — classifier JSON → skill → worker
- `schedule`, `media-file`, `web-search`, `zalo-context`
- model-router `POST /v1/classify`
