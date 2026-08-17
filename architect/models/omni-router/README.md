# OmniRouter (optional, v0.5.0)

## System architecture

| | |
|--|--|
| **Sits between** | Model Router ↔ general LLM providers |
| **Owns** | Optional general-task OpenAI-compatible gateway |
| **Does not own** | Coding-preferred path (9router) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">model-router</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>OmniRouter</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">LLM providers</td>
  </tr>
</table>

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
