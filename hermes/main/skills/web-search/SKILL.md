---
name: web-search
description: "Search the public web through the Router Worker web-search combo (Tavily → SearXNG). Do not invent backend API details."
---

# Web search skill

Stack:

```text
Hermes → this skill → Router Worker (OmniRouter side) → combo: Tavily → SearXNG
```

Search runs on the **Router Worker**, next to the LLM combos — not on the Media/File worker. The combo fails over in order; SearXNG is the local last resort so answers still work without vendor keys.

## Endpoints

| Purpose | Call |
|---------|------|
| Search | `POST http://model-router:8096/v1/search` `{ query, max_results?, backend? }` |
| Extract page text | `POST http://model-router:8096/v1/extract` `{ url }` (Tavily/Firecrawl only) |
| Current first backend | `GET http://model-router:8096/v1/backends/next` |

## Config

| Env | Meaning |
|-----|---------|
| `WEB_BACKENDS` | Combo order, default `tavily,searxng`; empty = search off |
| `TAVILY_API_KEY` / `FIRECRAWL_API_KEY` / `EXA_API_KEY` | Vendor members |
| `SEARXNG_URL` | Local SearXNG (default `http://searxng:8080`) |
| `WEB_SEARCH_MAX_RESULTS` | Result cap (default 3) |

## Do

1. Search only when classify `task_hint=search` or `skill=web_search`, or the instruction is clearly a live-web lookup (fuel, weather, FX).
2. Return short facts in the user's language. Do not dump raw JSON.
3. If every combo member fails, say so in one line. Do not fake prices.

## Do not

- Call the Media/File worker (`dispatcher:8090`) for search or extract — it no longer serves them
- Point ComfyUI or OCR at search
- Treat “không trích dẫn nguồn” as a knowledge-catalog lookup
- Browse GitHub/releases to “find an image URL” — that is media generation, not search

## Related

- `knowledge/web-search` — answer strategy and page-image OCR
- `searxng-search` — direct `SEARXNG_URL` curl examples (fallback only)
- `media-file` / `image-gen` — after facts are known, put them on a poster via `overlay`
