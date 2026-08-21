---
name: firecrawl
description: "Scrape/search/crawl via Firecrawl — prefer dispatcher; official vendor/firecrawl/* + API when needed. Needs FIRECRAWL_API_KEY."
---

# Firecrawl (Medium+)

Official packs:
- Agent API skill (this file) — runtime scrape/search
- Build skills: `vendor/firecrawl/firecrawl-build*` ([firecrawl/skills](https://github.com/firecrawl/skills))

## Prefer dispatcher

```bash
# Search (RR: tavily → firecrawl → searxng)
curl -sS -X POST http://model-router:8096/v1/search \
  -H 'content-type: application/json' \
  -d '{"q":"<query>","limit":5}'

# Extract / scrape when dispatcher exposes extract
curl -sS -X POST http://model-router:8096/v1/extract \
  -H 'content-type: application/json' \
  -d '{"url":"https://example.com"}'
```

Only call Firecrawl directly if dispatcher is down and `FIRECRAWL_API_KEY` is available.

## Direct API (fallback)

Base: `https://api.firecrawl.dev/v2` · Auth: `Authorization: Bearer $FIRECRAWL_API_KEY`

```python
import os, json, urllib.request

BASE = "https://api.firecrawl.dev/v2"
KEY = os.environ["FIRECRAWL_API_KEY"]

def firecrawl(endpoint, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}/{endpoint}",
        data=data,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())

# scrape → markdown
print(firecrawl("scrape", {"url": "https://example.com", "formats": ["markdown"]})["data"]["markdown"])

# search
for r in firecrawl("search", {"query": "…", "limit": 5}).get("data") or []:
    print(r.get("url"), r.get("title"))
```

## Related

- `tavily` / `research` — search policy + short user answers  
- `searxng` — free fallback when no paid keys  
- `vendor/firecrawl/*` — app-integration / onboarding docs
