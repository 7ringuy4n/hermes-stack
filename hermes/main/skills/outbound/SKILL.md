---
name: outbound
description: "Filter each assistant outbound line for Zalo/chat: send final user result only, drop process/status/noise. Prompt SoT is outbound.json. Never invent a user-facing reply — only label send|drop."
---

# Outbound (quiet delivery filter)

**Source of truth for the outbound prompt:** `hermes/main/skills/outbound/outbound.json`  
Do **not** hand-edit `architect/models/model-router/config/outbound.json` — sync from this file.

## When it runs

On each candidate assistant line before Zalo/Telegram delivery, the host may call model-router `POST /v1/outbound`. The LLM returns `{action: send|drop, text?: string}` using this prompt. Optional `text` is a privacy-cleaned send body (no chat/thread ids or folder/DM meta).

Structural path/secret redaction still applies on the host. This skill owns status-vs-result and identifier privacy — no host phrase regex for those.

## Prompt contract

Editable operators file: **`outbound.json`** (`system` + `user_template` + `timeout_s` / `temperature`).

## Sync (bake fallback)

Runtime: `/opt/data/skills/outbound/outbound.json` (skills mount).  
Bake: `architect/models/model-router/config/outbound.json` via:

```bash
bash scripts/main/sync-model-router-skills.sh
```

## Related

- `communication/quiet-delivery` — never send process/status frames
- `classify` — inbound purpose (separate SoT)
- model-router `POST /v1/outbound`
