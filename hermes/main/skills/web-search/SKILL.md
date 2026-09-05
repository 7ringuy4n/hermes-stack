---
name: web-search
description: "Search the public web via Omni combo web-search. Hermes calls Model Router which proxies to OmniRoute search with combo failover owned in Omni UI."
---

# Web search skill

Stack:

```text
Hermes native tool web_search (toolset web)
  → Model Router GET …/v1/searxng-compat (Omni-backed shim)
OR skill/HTTP (combo web-search):
Hermes → Model Router POST /v1/search
      → OmniRoute POST /v1/search `{ combo: web-search }`
      → operator members + failover in Omni UI (Tavily, Firecrawl, SearXNG, …)
```

Prefer the **native `web_search` tool**. On this stack Hermes `SEARXNG_URL`
points at Model Router `…/v1/searxng-compat` (Omni-backed). Fallback HTTP:
`POST http://model-router:8096/v1/search`.

**Combo `web-search`** owns search routing. Omni UI owns the **search combo**
members and provider connections. Do **not** call Omni chat
`/v1/chat/completions` to “search”. Do **not** call Media/File worker.

## Endpoints

| Purpose | Call |
|---------|------|
| Search | `POST http://model-router:8096/v1/search` `{ query, max_results? }` |
| Direct Omni (ops) | `POST http://omni-router:20129/v1/search` Bearer `OMNIROUTER_API_KEY` `{ query, max_results?, combo: web-search }` |
| Extract page text | `POST http://model-router:8096/v1/extract` `{ url }` (Tavily/Firecrawl; not SearXNG) |
| Current combo | `GET http://model-router:8096/v1/backends/next` |

## Config (operators)

| Env | Meaning |
|-----|---------|
| Omni Providers → Search | Connect **Tavily** + **Firecrawl** + **SearXNG** (`providerSpecificData.baseUrl=http://searxng:8080`) |
| Omni combo **web-search** | PRIORITY search providers (tavily-search, firecrawl-search, searxng-search, …) |
| `scripts/main/first-setup-omnirouter.py` | Ensures SearXNG connection, blocks `ollama-search`, verifies combo on API key ACL |
| `MODEL_ROUTER_WEB_SEARCH_COMBO` | Router combo name (default `web-search`) |
| `WEB_SEARCH_PROVIDER_TIMEOUT_S` | Per-request HTTP timeout (default 20s) |
| `WEB_EXTRACT_BACKENDS` | Extract order (`tavily,firecrawl`) |
| `OMNIROUTER_API_KEY` / `OMNIROUTER_BASE_URL` | Required for search |

## Do

1. Search only when classify `task_hint=search` or `skill=web_search`, or the instruction is clearly a live-web lookup (fuel, weather, FX, lyrics).
2. Return short facts in the user's language. Do not dump raw JSON.
3. If search returns empty, say so briefly — do not invent sources.

## Don't

1. Do not bypass Omni combo search with direct provider calls from Hermes.
2. Do not use SearXNG for page extract.
