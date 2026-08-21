---
name: searxng
description: Free meta-search via self-hosted SearXNG — dispatcher fallback or official searxng-search skill.
---

# SearXNG (Medium+)

Official upstream: [NousResearch/hermes-agent `optional-skills/research/searxng-search`](https://github.com/NousResearch/hermes-agent/blob/main/optional-skills/research/searxng-search/SKILL.md) → local folder **`searxng-search/`**.

## Prefer dispatcher

Medium compose runs SearXNG; dispatcher uses it when Tavily/Firecrawl miss or as last backend:

```bash
curl -sS -X POST http://model-router:8096/v1/search \
  -H 'content-type: application/json' \
  -d '{"q":"<query>","limit":5}'
```

## Direct (fallback)

Env in stack: `SEARXNG_URL=http://searxng:8080` (container) or host port `SEARXNG_PORT`.

```bash
curl -sS --max-time 10 \
  "${SEARXNG_URL}/search?q=<urlencoded>&format=json&limit=5"
```

Snippets only — for full page content use Firecrawl extract (`firecrawl` skill / dispatcher extract) after picking a URL.

Full curl/Python recipes → load **`searxng-search`**.
