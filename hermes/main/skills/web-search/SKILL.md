---
name: web-search
description: "Search the public web via Omni combo web-search. Hermes calls Router Worker which proxies to OmniRoute search with combo failover owned in Omni UI."
---

# Web search skill

Stack:

```text
Hermes native tool web_search (toolset web)
  → Router Worker GET …/v1/searxng-compat (Omni-backed shim)
OR skill/HTTP (combo web-search):
Hermes → Router Worker POST /v1/search
      → OmniRoute POST /v1/search `{ combo: web-search }`
      → operator members + failover in Omni UI (Tavily, Firecrawl, SearXNG, …)
      → internal SearXNG when OmniRoute is unavailable
```

Prefer the **native `web_search` tool**. On this stack Hermes `SEARXNG_URL`
points at Router Worker `…/v1/searxng-compat` (Omni-backed). Fallback HTTP:
`POST http://router-worker:8096/v1/search`.

**Combo `web-search`** owns search routing. Omni UI owns the **search combo**
members and provider connections. Do **not** call Omni chat
`/v1/chat/completions` to “search”. Do **not** call Media/File worker.

## Endpoints

| Purpose | Call |
|---------|------|
| Search | `POST http://router-worker:8096/v1/search` `{ query, max_results? }` |
| Direct Omni (ops) | `POST http://omni-router:20129/v1/search` Bearer `OMNIROUTER_API_KEY` `{ query, max_results?, combo: web-search }` |
| Extract page text | `POST http://router-worker:8096/v1/extract` `{ url }` (Tavily/Firecrawl; not SearXNG) |
| Current combo | `GET http://router-worker:8096/v1/backends/next` |

## Config (operators)

| Env | Meaning |
|-----|---------|
| Omni Providers → Search | Connect **Tavily** + **Firecrawl** + **SearXNG** (`providerSpecificData.baseUrl=http://searxng:8080`) |
| Omni combo **web-search** | PRIORITY search providers (tavily-search, firecrawl-search, searxng-search, …) |
| `scripts/main/first-setup-omnirouter.py` | Ensures SearXNG connection, blocks `ollama-search`, verifies combo on API key ACL |
| `ROUTER_WORKER_WEB_SEARCH_COMBO` | Router combo name (default `web-search`) |
| `WEB_SEARCH_PROVIDER_TIMEOUT_S` | Per-request HTTP timeout (default 20s) |
| Page extraction | Uses available OpenBao-backed Tavily/Firecrawl credentials without an env ordering pin. |
| `FALLBACK_SEARXNG_URL` | Search-only fallback after OmniRoute. |
| `OMNIROUTER_API_KEY` / `OMNIROUTER_BASE_URL` | Required for search |

## Do

1. Search only when classify `task_hint=search` or `skill=web_search`, or the instruction is clearly a live-web lookup (fuel, weather, FX, lyrics).
2. Return short facts in the user's language. Do not dump raw JSON.
3. If search returns empty, say so briefly — do not invent sources.

## Don't

1. Do not bypass Router Worker with direct provider calls from Hermes.
2. Do not use SearXNG for page extract.
3. Do not use `execute_code`, terminal commands, or language HTTP libraries as
   a substitute for native `web_search`. A current lookup needs a fresh native
   search call in that turn even when conversation history contains an older answer.
