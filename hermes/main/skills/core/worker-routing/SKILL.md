---
name: worker-routing
description: "Route classifier JSON to the correct worker skill. LLM classifies; Hermes validates and delegates — never re-parse user prose."
---

# Worker routing (classifier → skill → worker)

Hermes receives structured JSON from the model-router `/v1/classify` hop (or equivalent). **Do not** infer intent from keywords. Read the JSON fields and follow this table.

| `task_hint` | `skill` | `skill_action` | Worker / next step |
|---|---|---|---|
| `normal` | `null` | `null` | Hermes via model-router chat combo (`ack_then_deliver`). No host instant reply. |
| `search` | `web_search` | `search` | **Web Search skill** → Router Worker `POST /v1/search` → Omni (Tavily → Firecrawl → SearXNG). |
| `file` / `tool` (media) | `media_file` | `process_file`, `process_image`, `generate_media`, `create_file` | **Media/File skill** → media worker / OCR (**PaddleOCR first** on `ocr:8091`) / ingest extract for office (`/v1/extract-text`) / ingest archive media-only (`/v1/extract-archive`) / ComfyUI (`/v1/media/text` for audio-video) / **create-and-send office PDF via `file-gen` → Dispatcher `/v1/office-file`** (never local `pdf` skill, never pip reportlab). Never local docx/terminal forensics for chat attachment reads. |
| `schedule` | `schedule` | `create` | **Schedule skill** → Go schedule worker (`SCHEDULE_URL`). Store inner `fire_text` only. |
| `knowledge` | `knowledge` | `lookup` | Knowledge catalog (top 5). Not live web search. |
| `coding` | `null` or coding skills | — | Router worker → 9router (coding path). Gateway skips rate limit on coding paths. |

## Execution modes

| `execution_class` | `response_mode` | Hermes behavior |
|---|---|---|
| `interactive` | `ack_then_deliver` | Route through model-router; Hermes chat combo produces the reply. |
| `async` | `ack_then_deliver` | Workflow / worker job; deliver when done. |
| `schedule` | `confirm` | Confirm lịch once; worker fires inner message later. |

Legacy `response_mode: direct` is remapped to `ack_then_deliver` at normalize time — do not emit it from classify.

## Multi-instruction messages

When `instructions[]` has **N > 1** distinct deliverables:

1. Keep **N** separate instructions in order — the Zalo host runs them **sequentially over time** (one turn at a time, multiple replies/files), not in one combined answer.
2. Use `depends_on=[i]` only when a later instruction truly needs output from instruction `i` (e.g. search → office file). Independent parts use `depends_on=[]`.
3. Do **not** merge numbered greeting + fuel + weather + draw-image into one poster unless the user asked for one combined image.

## Scheduled fire (`scheduleFire`)

When inbound carries `scheduleFire: true`:

- If `scheduleDelivery` / `schedule_delivery` is **`verbatim`** (or `send`/`deliver`): the host **sends `fire_text` as-is** — do not paraphrase or re-chat. Dictated send-bodies stay verbatim even when the payload contains words that look like skills.
- If delivery is **`process`** (default for task schedules): treat payload as **inner work only** (not “đặt lịch lúc HH:MM”), classify again if needed, then route per table above.
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
- Classifier contract: `hermes/main/skills/classify/` (parts assembled into one hop; model-router loads it)
