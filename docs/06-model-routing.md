# Model routing and OmniRoute

## Responsibilities

`model-router` is the internal task-aware OpenAI-compatible proxy. It
normalizes requests, carries attribution headers, invokes classification, and
selects a named capability. **OmniRoute** owns provider accounts, combo
membership, priority/fallback strategy, request history, and provider health.

```text
caller → model-router → OmniRoute named combo → provider member
```

When OmniRoute is unhealthy or intentionally inactive, Model Router continues
only through explicitly configured capability-compatible providers. Chat,
vision, embeddings, still generation, and image edits have separate model
declarations; web search uses the internal SearXNG fallback. Office files use
the chat/content fallback and remain rendered by Dispatcher. A provider is
never assumed to support an endpoint from its name.

The names `omnirouter`, `OMNIROUTER_*`, and `first-setup-omnirouter` remain in
compose and scripts as compatibility interfaces. They refer to OmniRoute; no
second OmniRouter or 9Router service is supported.

## Active combo contract

All managed combos use `priority`. Setup may ensure a combo exists and may
repair required metadata, but update must preserve operator-managed provider
order and membership.

| Combo | Purpose | Typical API path |
|---|---|---|
| `hermes` | Interactive chat and user-facing prose | `/v1/chat/completions` |
| `classifier` | Structured classify result | `/v1/chat/completions` |
| `web-search` | Web retrieval providers | combo-specific compatible path |
| `image-gen` | New still images | `/v1/images/generations` |
| `vision-ocr` | Natural image/document analysis | `/v1/chat/completions` with media |
| `embedding` | Knowledge and memory vectors | `/v1/embeddings` |
| `image-edit` | Edit an attached or reply-quoted image | image edit compatible path |

`video-gen` and `video-edit` are deliberately absent. Do not restore their
skills, combos, routes, or tests without a separately verified provider and an
explicit product decision.

## Classification

Classification uses one LLM hop and one JSON contract. Prompt source of truth:

- `hermes/main/skills/classify/classify.json`
- `hermes/main/skills/classify/parts/*.md`

The parts must remain English, general-purpose, and future-safe. Do not embed
request-specific examples such as a fixed poster, city, weather scene, or
Vietnamese phrase in application code. The current message language controls
user-visible generated text; safety and profanity constraints apply in that
language.

The classifier structures work; it does not answer the user. Deterministic
host code validates the returned schema and dispatches the selected skill.

## Setup and update behavior

`bash run.sh first-setup-omnirouter` is setup-only. It initializes the
OmniRoute API/access path and required combo shells. It must not send user test
messages. `bash run.sh update` repairs stack wiring while preserving current
providers, AI Box accounts, combo members, order, and strategy.

Use OmniRoute UI/API for manual provider changes. A configuration change is
valid only after an export/backup and a diff proving unrelated combos were not
modified.

## Health and timeouts

- `/v1/models` may return `401` when the service is healthy but the caller is
  unauthenticated. UI `/` may redirect. Health checks accept the documented
  status set instead of treating either as a crash.
- Queue-budget errors are saturation signals, not upstream timeouts. Do not
  hide them with test sleeps. Record queue wait, provider latency, and outcome.
- Image generation/editing may take up to five minutes; chat/classification
  uses shorter operation-specific deadlines.
- Free/quota-limited provider cases are `SKIP` only with captured provider
  evidence. Functional failures must never be relabeled `PASS`.

## Configuration

| Setting | Meaning |
|---|---|
| `ENABLE_MODEL_ROUTER=active` | Run the internal proxy. |
| `ENABLE_OMNIROUTER=active` | Run OmniRoute via the compatibility profile. |
| `OMNIROUTER_DEFAULT_COMBO=hermes` | Default chat combo. |
| `OMNIROUTER_CLASSIFY_COMBO=classifier` | Classify combo. |
| `IMAGE_GEN_COMBO=image-gen` | Still-image generation combo. |
| `VISION_OCR_COMBO=vision-ocr` | Image/document analysis combo. |
| `EMBEDDING_MODEL=embedding` | Embedding combo alias. |
| `HERMES_REPLICAS=1` | Single-host Hermes replica count. |
| `MODEL_ROUTER_FALLBACK_PROVIDER_ORDER` | Priority list of explicitly configured compatible provider profiles. |
| `<PROVIDER>_*_MODEL` | Per-capability model; the matching API key is held in OpenBao. |
| `FALLBACK_SEARXNG_URL` | Search fallback used after/unavailable OmniRoute. |

See [architect/models/model-router/README.md](../architect/models/model-router/README.md)
and [config/DEFAULTS.md](./config/DEFAULTS.md).
