# Case: web search backend chain

Verify which engine handles `/v1/search` and fallback order.

## Default engine (Medium/High)

Profile sets `WEB_BACKENDS=tavily,firecrawl`. Dispatcher:

1. Round-robin first paid backend
2. On failure, tries others in `WEB_BACKENDS`
3. **Always appends SearXNG** as last resort when backends non-empty

Low: `WEB_BACKENDS` empty → 503 controlled error.

## Steps (unit/local)

1. Run `python test/scripts/web_search_backends_unit.py`
2. Assert `/health` lists `backends` array
3. POST `/v1/search` with `{"query":"weather Ho Chi Minh","max_results":3}`
4. Record `backend` field in JSON response

## Steps (lab)

1. Case 04 weather query via Hermes
2. Compare dispatcher response `backend` with env `WEB_BACKENDS`
3. Disable Tavily key → expect Firecrawl or SearXNG attempt (record which)

## Pass criteria

- Search returns `backend` ∈ {tavily, firecrawl, searxng, exa}
- Low profile: 503 + short message, no crash
- Hermes does not fabricate weather when all backends down

## Fail events

- Empty fake results when backend down
- No `backend` field logged
