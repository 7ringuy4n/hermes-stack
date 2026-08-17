# OmniRouter (optional, v0.5.0)

## Purpose

Separate OpenAI-compatible LLM gateway for **general / non-coding** tasks. Used by the Model Router when `ENABLE_OMNIROUTER=1`.

## Defaults

- Image: `${OMNIROUTER_IMAGE}` (set in `.env` — separate image/repo from 9router)
- Port: host `127.0.0.1:${OMNIROUTER_HOST_PORT:-20129}:20129`
- Combo: OpenCode Free + all its models (same *style* as 9router `hermes` combo) via `scripts/main/first-setup-omnirouter.sh`

## Routing

| Both up | Coding → 9router · Other → OmniRouter |
| Only OmniRouter | Coding + other → OmniRouter · then direct LLM pool |
| Only 9router | All → 9router · then pool |

## Enable

```bash
ENABLE_OMNIROUTER=1
OMNIROUTER_IMAGE=...   # required when enabled
OMNIROUTER_INITIAL_PASSWORD=...
```

Component uses compose profile `omnirouter`.
