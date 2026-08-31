---
name: web-search
description: "Search the public web via combo web-search: OmniRoute search combo then direct adapters. Hermes calls Router Worker which proxies with failover."
---

# Web search skill

Stack:

```text
Hermes native tool web_search (toolset web)
  → Tavily (TAVILY_API_KEY) → SearXNG shim (SEARXNG_URL) …
OR skill/HTTP (combo web-search):
Hermes → Router Worker POST /v1/search
      → backends: omni (combo web-search) — optional WEB_BACKENDS for direct adapters
      → OmniRoute POST /v1/search `{ combo: web-search }` only
```

Prefer the **native `web_search` tool**. On this stack Hermes `SEARXNG_URL`
points at Router Worker `…/v1/searxng-compat` (Omni-backed). Optional:
`TAVILY_API_KEY` in Hermes env for direct Tavily. Fallback HTTP:
`POST http://model-router:8096/v1/search`.

**Combo `web-search`** owns Router failover order. Omni UI owns the **search
combo** members and provider connections. Do **not** call Omni chat
`/v1/chat/completions` to “search”. Do **not** call Media/File worker.

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
| Omni combo **web-search** | PRIORITY search providers (tavily-search, firecrawl-search, searxng-search, …) |
| `scripts/main/first-setup-omnirouter.py` | Ensures SearXNG connection, blocks `ollama-search`, pins combo env chain |
| `MODEL_ROUTER_WEB_SEARCH_COMBO` | Router combo name (default `web-search`) |
| `WEB_SEARCH_PROVIDER_TIMEOUT_S` | Per-provider HTTP timeout (default 20s) for fast failover |
| `WEB_BACKENDS` | Optional lab override (`tavily,searxng`, …). Default: **omni combo only** when `OMNIROUTER_*` set |
| `hermes/main/skills/web-search/web-search-combo.json` | Documents combo name `web-search` (operator members live in Omni UI) |
| `WEB_EXTRACT_BACKENDS` | Extract order (`tavily,firecrawl`) |
| `OMNIROUTER_API_KEY` / `OMNIROUTER_BASE_URL` | Required for `omni` backend |

## Do

1. Search only when classify `task_hint=search` or `skill=web_search`, or the instruction is clearly a live-web lookup (fuel, weather, FX, lyrics).
2. Return short facts in the user's language. Do not dump raw JSON.
3. If search returns empty, say so briefly — do not invent sources.

## Don't

1. Do not hang the turn on one provider; Router Worker fails over with short timeouts.
2. Do not use SearXNG for page extract.
