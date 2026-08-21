---
name: worker-routing
description: "Route classifier JSON to the correct worker skill. LLM classifies; Hermes validates and delegates — never re-parse user prose."
---

# Worker routing (classifier → skill → worker)

Hermes receives structured JSON from the model-router `/v1/classify` hop (or equivalent). **Do not** infer intent from keywords. Read the JSON fields and follow this table.

| `task_hint` | `skill` | `skill_action` | Worker / next step |
|---|---|---|---|
| `normal` | `null` | `null` | Answer directly. **No** workflow queue for simple chat. |
| `search` | `web_search` | `search` | **Web Search skill** → Router Worker `POST /v1/search` (combo Tavily → SearXNG). |
| `file` / `tool` (media) | `media_file` | `process_file`, `process_image`, `generate_media`, `create_file` | **Media/File skill** → media worker / OCR (**PaddleOCR first** on `ocr:8091`) / ComfyUI (`/v1/media/text` for audio-video). |
| `schedule` | `schedule` | `create` | **Schedule skill** → Go schedule worker (`SCHEDULE_URL`). Store inner `fire_text` only. |
| `knowledge` | `knowledge` | `lookup` | Knowledge catalog (top 5). Not live web search. |
| `coding` | `null` or coding skills | — | Router worker → 9router (coding path). Gateway skips rate limit on coding paths. |

## Execution modes

| `execution_class` | `response_mode` | Hermes behavior |
|---|---|---|
| `interactive` | `direct` | Reply in the same turn. |
| `async` | `ack_then_deliver` | Short ack, then workflow / worker; deliver when done. |
| `schedule` | `confirm` | Confirm lịch once; worker fires inner message later. |

## Multi-instruction messages

When `instructions[]` has **N > 1** distinct deliverables:

1. Keep **N** separate workflow jobs unless `depends_on` requires order.
2. Default **parallel** (`sequential=false`) unless an instruction depends on another.
3. Do **not** merge numbered greeting + fuel + weather + draw-image into one poster unless the user asked for one combined image.

## Scheduled fire (`scheduleFire`)

When inbound carries `scheduleFire: true`:

- Treat payload as **inner work only** (not “đặt lịch lúc HH:MM”).
- Classify again if needed, then route per table above.
- **Do not** create another schedule for the same fire.

## Worker availability

Optional workers are off unless the host enables them:

| Component | Flag | Skill |
|---|---|---|
| Schedule Worker | `ENABLE_SCHEDULE=1` | `schedule` |
| Media/File Worker | `ENABLE_MEDIA_FILE=1` | `media_file` |
| Message Worker (Zalo/Telegram/…) | `ENABLE_MESSAGE=1` | platform plugin |
| Notification Worker | `ENABLE_NOTIFY=1` | notify service |
| Security Worker | `ENABLE_SECURITY=1` | `security` |

If a required worker is disabled, say so in one line — do not invent a local substitute.

## Related skills

- `schedule`, `web-search`, `media-file`, `security`, `core/scheduling`
- Classifier contract: `architect/models/model-router/config/classify.json`
