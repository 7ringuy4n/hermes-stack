---
name: outbound
description: "Filter each assistant outbound messaging line: send final user result only, drop process/status/noise. Prompt SoT is outbound.json. Never invent a user-facing reply — only label send|drop."
---

# Outbound (quiet delivery filter)

**Source of truth for the outbound prompt:** `hermes/main/skills/outbound/outbound.json`  
Do **not** hand-edit `architect/models/router-worker/config/outbound.json` — sync from this file.

## When it runs

On each candidate assistant line before channel delivery, the host may call router-worker `POST /v1/outbound`. The LLM returns `{action: send|drop, text?: string}` using this prompt. Optional `text` is a privacy-cleaned send body (no chat/thread ids or folder/direct-message meta).

Structural path/secret redaction still applies on the host. This skill owns status-vs-result and identifier privacy — no host phrase regex for those.

## Prompt contract

Editable operators file: **`outbound.json`** (`system` + `user_template` + `timeout_s` / `temperature`).

## Sync (bake fallback)

Runtime: `/opt/data/skills/outbound/outbound.json` (skills mount).  
Bake: `architect/models/router-worker/config/outbound.json` via:

```bash
bash scripts/main/sync-router-worker-skills.sh
```

## Related

- `communication/quiet-delivery` — never send process/status frames
- `classify` — inbound purpose (separate SoT)
- router-worker `POST /v1/outbound`
