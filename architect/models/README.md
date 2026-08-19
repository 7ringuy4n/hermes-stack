# models

## System architecture

| | |
|--|--|
| **Sits between** | Hermes ↔ LLM providers / tool HTTP |
| **Owns** | Model Router, 9router, optional OmniRouter, dispatcher (search/media helpers) |
| **Does not own** | Hermes skills (those live under `hermes/main/skills`) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Hermes</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>model-router · dispatcher</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">9router / Omni · web backends</td>
  </tr>
</table>

## Purpose

Model gateway and tool bus: **Model Router** (task_hint → providers), **9Router** / optional **OmniRouter**, and **dispatcher** (web search, media helpers). Hermes talks here instead of hardcoding vendors in skills. Security is **Secret Probe**, not a task type.

## Profile

| Piece | Low | Medium | High |
|---|---|---|---|
| model-router | Must (default on) | Must | Must |
| dispatcher | Must (web backends empty) | Must + Tavily→Firecrawl→SearXNG | Same |
| 9router | Must | Must | Must |
| OmniRouter | Off | Optional | Optional (`ENABLE_OMNIROUTER`; pairs with `omni-exporter` when metrics are on) |

## Sub-packages

| Package | Function |
|---|---|
| [model-router/](./model-router/README.md) | Hybrid task class → 9router / Omni / fallback |
| [omni-router/](./omni-router/README.md) | Optional general-task router (separate image) |
| [dispatcher/](./dispatcher/README.md) | `/v1/search`, image/office helpers, tool HTTP APIs |

## How it works

```text
Hermes needs a completion
    → INPUT Secret Probe (BLOCK stops)
    → model-router task_hint
        → coding  → 9router (when up)
        → normal / others → OmniRouter (if enabled) else 9router / pool
        → clear no_model_available if nothing left
    → OUTPUT Secret Probe

Hermes / skill needs web search (Medium+)
    → dispatcher /v1/search
    → Tavily → Firecrawl → SearXNG (top 5)
```

On **Low**, do not use dispatcher for internet answers to knowledge questions — knowledge stays in ingest/Qdrant.

## Related

- [docs/06-model-routing.md](../../docs/06-model-routing.md)  
- [tools](../tools/README.md)  
- [hermes/main/skills/research](../../hermes/main/skills/research/SKILL.md)
