---
name: web-search
description: "Search the public web through OmniRoute (UI owns Tavily → Firecrawl → SearXNG). Hermes calls Router Worker which proxies to Omni."
---

# Web search skill

Stack:

```text
Hermes native tool web_search (toolset web)
  → Tavily (TAVILY_API_KEY) → SearXNG shim (SEARXNG_URL) …
OR skill/HTTP:
Hermes → Router Worker POST /v1/search (backend omni)
      → OmniRoute POST /v1/search (Omni UI: Tavily → Firecrawl → SearXNG)
```

Prefer the **native `web_search` tool**. On this stack Hermes `SEARXNG_URL`
points at Router Worker `…/v1/searxng-compat` (Omni-backed). Optional:
`TAVILY_API_KEY` in Hermes env for direct Tavily. Fallback HTTP:
`POST http://model-router:8096/v1/search`.

**Omni UI owns** Search provider connections for the Router Worker / Omni path.
Do **not** call Omni chat `/v1/chat/completions` to “search”. Do **not** call
Media/File worker.

## Endpoints

| Purpose | Call |
|---------|------|
| Search | `POST http://model-router:8096/v1/search` `{ query, max_results? }` |
| Direct Omni (ops) | `POST http://omni-router:20129/v1/search` Bearer `OMNIROUTER_API_KEY` `{ query, max_results? }` |
| Extract page text | `POST http://model-router:8096/v1/extract` `{ url }` (Tavily/Firecrawl; not SearXNG) |
| Current combo head | `GET http://model-router:8096/v1/backends/next` |

## Config (operators)

| Env / file | Meaning |
|------------|---------|
| Omni Providers → Search | Connect **Tavily** + **Firecrawl** + **SearXNG** (`providerSpecificData.baseUrl=http://searxng:8080`) |
| `scripts/main/first-setup-omnirouter.sh` | Ensures SearXNG connection, priorities Tavily→Firecrawl→SearXNG, blocks `ollama-search` |
| `OMNIROUTER_SEARCH_PROVIDERS` | Default `tavily-search,firecrawl-search,searxng-search` |
| `WEB_SEARCH_PROVIDER_TIMEOUT_S` | Per-provider HTTP timeout (default 20s) for fast failover |
| `WEB_BACKENDS` | Default `omni` (proxy). Use `tavily,firecrawl,searxng` only if Omni is off |
| `hermes/main/skills/web-search/web-search-combo.json` | SoT combo (`backends: ["omni"]`); bake fallback under model-router `config/` |
| `WEB_EXTRACT_BACKENDS` | Extract order (`tavily,firecrawl`) |
| `OMNIROUTER_API_KEY` / `OMNIROUTER_BASE_URL` | Required for `omni` backend |

## Do

1. Search only when classify `task_hint=search` or `skill=web_search`, or the instruction is clearly a live-web lookup (fuel, weather, FX, lyrics).
2. Return short facts in the user's language. Do not dump raw JSON.
3. If search returns empty, say so briefly — do not invent sources.

## Don't

1. Do not hang the turn on one provider; Router Worker fails over with short timeouts.
2. Do not use SearXNG for page extract.
