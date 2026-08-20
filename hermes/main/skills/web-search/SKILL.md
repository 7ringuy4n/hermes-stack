---
name: web-search
description: "Search the public web through OmniRouter → SearXNG. Do not invent SearXNG API details."
---

# Web search skill

Stack:

```text
Hermes → this skill → OmniRouter → SearXNG
```

Prefer the existing Hermes web toolset when it is configured. If you need an HTTP fallback, call OmniRouter/SearXNG through the stack URLs — do not hard-code engine names or scrape result HTML.

## Config

- `SEARXNG_URL` (default `http://searxng:8080`)
- Model-router / OmniRouter already front the LLM. Search traffic stays on SearXNG.

## Do

1. Search only when classify `task_hint=search` or `skill=web_search`, or the current instruction is clearly a live-web lookup (fuel, weather, FX).
2. Return short facts in the user’s language. Do not dump raw JSON.
3. If SearXNG is down, say so in one line. Do not fake prices.

## Do not

- Point ComfyUI or OCR at search
- Treat “không trích dẫn nguồn” as a knowledge-catalog lookup
- Browse GitHub/releases to “find an image URL” — that is media generation, not search

## Related

- `searxng-search` — curl examples against `SEARXNG_URL`
- `media-file` / `image-gen` — after facts are known, put them on a poster via `overlay`
