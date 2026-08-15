# models

## Purpose

Model gateway and tool bus: **9Router** (LLM provider fan-out) and **dispatcher** (web search, media helpers, OpenAI-compatible proxy routes). Hermes ModelManager / ToolManager talk here instead of hardcoding vendors in skills.

## Profile

| Piece | Low | Medium | High |
|---|---|---|---|
| dispatcher | Must (web backends empty) | Must + Tavily→Firecrawl→SearXNG | Same |
| 9router | Must (wire vendor image in next slice) | Must | Must |

## Sub-packages

| Package | Function |
|---|---|
| [dispatcher/](./dispatcher/README.md) | `/v1/search`, mode hints, tool HTTP APIs |

## How it works

```text
Hermes needs a completion
    → 9Router → provider models (failover)

Hermes / skill needs web search (Medium+)
    → dispatcher /v1/search
    → Tavily → Firecrawl → SearXNG (top 5)
```

On **Low**, do not use dispatcher for internet answers to knowledge questions — knowledge stays in ingest/Qdrant.

## Related

- [tools](../tools/README.md)  
- [hermes/main/skills/research](../../hermes/main/skills/research/SKILL.md)
