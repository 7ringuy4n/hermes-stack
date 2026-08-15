---
name: tavily
description: "Web search/extract via Tavily — prefer dispatcher /v1/search; deep ops use vendor/tavily/* official skills."
---

# Tavily (Medium+)

Upstream pack: [`tavily-ai/skills`](https://github.com/tavily-ai/skills) vendored at `skills/vendor/tavily/`.

## Prefer dispatcher (keys in compose)

```bash
curl -sS -X POST http://dispatcher:8090/v1/search \
  -H 'content-type: application/json' \
  -d '{"q":"<query>","limit":5}'
```

Chain (default Medium+): **Tavily → Firecrawl → SearXNG**. Do not call `api.tavily.com` directly unless dispatcher is down and `TAVILY_API_KEY` is in the Hermes env.

## Deeper Tavily skills

| Skill | Role |
|---|---|
| `vendor/tavily/tavily-search` | Search |
| `vendor/tavily/tavily-extract` | Extract URLs |
| `vendor/tavily/tavily-crawl` / `tavily-map` | Crawl / map |
| `vendor/tavily/tavily-research` | Deep research |
| `vendor/tavily/tavily-best-practices` | When to use which |

User reply: short summary + 2–5 bullets + sources (`research` + `common-rules`).
