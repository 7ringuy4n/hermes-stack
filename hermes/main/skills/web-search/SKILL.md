---
name: web-search
description: "Search the public web through the Router Worker websearch combo (config: Tavily → SearXNG). Do not invent backend API details."
---

# Web search skill

Stack:

```text
Hermes → this skill → Router Worker (model-router /v1/search)
                    → combo "websearch" failover: Tavily → SearXNG (local)
```

**Always** call Router Worker. Do **not** call OmniRouter for search (OmniRouter is LLM
chat combos only). Do **not** call Media/File worker for search.

Failover order is **not** coded in the skill. It comes from:

1. Env `WEB_BACKENDS` (comma list), or
2. Router Worker file `config/web-search-combo.json` (`backends`: `tavily`, `searxng`)

## Endpoints

| Purpose | Call |
|---------|------|
| Search | `POST http://model-router:8096/v1/search` `{ query, max_results?, backend? }` |
| Extract page text | `POST http://model-router:8096/v1/extract` `{ url }` (extract backends from config; not SearXNG) |
| Current combo head | `GET http://model-router:8096/v1/backends/next` |

## Config (operators)

| Env / file | Meaning |
|------------|---------|
| `config/web-search-combo.json` | Default combo name + backends + extract_backends |
| `WEB_BACKENDS` | Override failover order (`tavily,searxng`); empty = search off |
| `WEB_EXTRACT_BACKENDS` | Override extract order (`tavily,firecrawl`) |
| `TAVILY_API_KEY` / `FIRECRAWL_API_KEY` / `EXA_API_KEY` | Vendor members |
| `SEARXNG_URL` | Local SearXNG (default `http://searxng:8080`) |
| `WEB_SEARCH_MAX_RESULTS` | Result cap |

## Do

1. Search only when classify `task_hint=search` or `skill=web_search`, or the instruction is clearly a live-web lookup (fuel, weather, FX, lyrics).
2. Return short facts in the user's language. Do not dump raw JSON.
3. If every combo member fails, say so in one line. Do not fake prices.

## Do not

- Call the Media/File worker (`dispatcher:8090`) for search or extract
- Call OmniRouter `/v1/chat/completions` to “search”
- Hardcode Tavily or SearXNG URLs / order in prompts
- Browse GitHub/releases to “find an image URL” — that is media generation, not search

## Related

- `knowledge/web-search` — answer strategy and page-image OCR
- `searxng-search` — direct `SEARXNG_URL` examples (ops only; prefer Router Worker)
- `media-file` / `image-gen` — after facts are known, put them on a poster via `overlay`
