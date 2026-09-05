# models

## System architecture

| | |
|--|--|
| **Sits between** | Hermes ↔ LLM providers / tool HTTP |
| **Owns** | Model Router, omni-router, optional OmniRouter, dispatcher (search/media helpers) |
| **Does not own** | Hermes skills (those live under `hermes/main/skills`) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Hermes</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>model-router · dispatcher</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">omni-router / Omni · web backends</td>
  </tr>
</table>

## Purpose

Model gateway and tool bus: **Model Router** (task_hint → providers), **OmniRoute** / optional **OmniRouter**, and **dispatcher** (web search, media helpers). Hermes talks here instead of hardcoding vendors in skills. Security is **Secret Probe**, not a task type.

`omni-attribution/` completes missing call-log attribution for stack-owned non-chat OmniRoute endpoints. It is isolated from routing and never changes providers, combo definitions, or combo membership.

## Profile

| Piece | Low | Medium | High |
|---|---|---|---|
| model-router | Must (default on) | Must | Must |
| dispatcher | Must (web backends empty) | Must + Tavily→Firecrawl→SearXNG | Same |
| omni-router | Must | Must | Must |
| OmniRouter | Off | Optional | Optional (`ENABLE_OMNIROUTER`; pairs with `omni-exporter` when metrics are on) |

## Sub-packages

| Package | Function |
|---|---|
| [model-router/](./model-router/README.md) | Hybrid task class → omni-router / Omni / fallback |
| [omni-router/](./omni-router/README.md) | Optional general-task router (separate image) |
| [dispatcher/](./dispatcher/README.md) | Media helpers; points Hermes to model-router for `/v1/search` |

## How it works

```text
Hermes needs a completion
    → INPUT Secret Probe (BLOCK stops)
    → model-router task_hint
        → coding  → omni-router (when up)
        → normal / others → OmniRouter (if enabled) else omni-router / pool
        → clear no_model_available if nothing left
    → OUTPUT Secret Probe

Hermes / skill needs web search (Medium+)
    → model-router /v1/search  (Model Router combo "websearch")
    → Omni combo web-search (operator failover in Omni UI)
      (default tavily → searxng)
    → extract via WEB_EXTRACT_BACKENDS / config (not SearXNG)
```

**Note:** OmniRouter does **not** host web search. Its combos are LLM models only.
SearXNG is a sibling container called by Model Router, not an OmniRouter plugin.

On **Low**, do not use dispatcher for internet answers to knowledge questions — knowledge stays in ingest/Qdrant.

## Related

- [docs/06-model-routing.md](../../docs/06-model-routing.md)  
- [tools](../tools/README.md)  
- [hermes/main/skills/research](../../hermes/main/skills/research/SKILL.md)
