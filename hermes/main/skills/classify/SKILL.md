---
name: classify
description: "Classify every inbound Zalo (and host) user message into structured purpose JSON. Prompt SoT is classify.json in this skill. Never reply to the user — only return JSON fields for routing."
---

# Classify (Zalo inbound purpose)

**Source of truth for the classify prompt:** `hermes/main/skills/classify/classify.json`  
Do **not** edit a second copy under `architect/models/model-router/config/` by hand — sync from this file (see below).

## When it runs

On **every new Zalo user message** (and gateway/host classify hops), the host must:

1. Strip Valkey `[Prior conversation]` wrappers for the classify input.
2. Call model-router `POST /v1/classify` (combo `classifier` / `MODEL_ROUTER_CLASSIFY_MODEL`).
3. Consume the structured JSON only (`task_hint`, `task_type`, `skill`, `skill_action`, `instructions`, schedule fields, `target_channel`, …).
4. Route via `core/worker-routing` / Zalo adapter — **never** re-parse Vietnamese prose with regex dictionaries.

Classify **never** sends a user-facing chat reply. It only structures work.

## Prompt contract

Editable operators file: **`classify.json`** in this folder (`system` + `user_template` + `timeout_s` / `temperature`).

Illustrations in the prompt are families, not an exhaustive dictionary. Paraphrases must still map to the same JSON fields.

## Sync (bake fallback)

Router-worker prefers this skill path at runtime (`/opt/data/skills/classify/classify.json`).  
Image bake still ships `architect/models/model-router/config/classify.json` as fallback:

```bash
bash scripts/main/sync-model-router-skills.sh
```

`run.sh update` / image rebuild should keep the fallback copy identical to this skill file.

## Must follow

1. One SoT prompt — this skill’s `classify.json`.
2. Host validates enums / protocol only; no keyword NLU for intent.
3. List/inspect ≠ delete; create schedules need temporal fields; destination names go in `target_channel`.
4. After editing the prompt, sync the bake fallback and recreate `router-worker` so the combo loads it.

## Related

- `core/worker-routing` — classifier JSON → skill → worker
- `schedule`, `media-file`, `web-search`, `zalo-context`
- model-router `POST /v1/classify`
