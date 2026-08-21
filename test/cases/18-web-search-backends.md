# Case: web search combo chain (Router Worker)

Verify which backend answers `/v1/search` on **router-worker** (`model-router:8096`) and the failover order.

## Default combo

`WEB_BACKENDS=tavily,searxng` (media worker activation keeps the same order):

1. Paid vendor first (Tavily; Firecrawl/Exa only when listed in `WEB_BACKENDS`)
2. On failure, the next combo member runs
3. **SearXNG is last** — local, no key needed

Empty `WEB_BACKENDS` with no `SEARXNG_URL` → 503 controlled error.

## Steps (unit/local)

1. Run `python test/scripts/web_search_backends_unit.py`
2. Assert `/health` lists `web_backends`
3. POST `/v1/search` with `{"query":"weather Ho Chi Minh","max_results":3}`
4. Record the `backend` field in the JSON response

## Steps (lab)

1. Case 04 weather query via Zalo → Hermes
2. Compare the response `backend` with env `WEB_BACKENDS`
3. Remove the Tavily key → expect SearXNG to answer (record which)
4. Confirm the media worker no longer serves search: `POST dispatcher:8090/v1/search` → 404

## Pass criteria

- Search returns `backend` ∈ {tavily, firecrawl, searxng, exa} (or `+` joined combo)
- No backends configured: 503 + short message, no crash
- Hermes does not fabricate weather/fuel when every member fails
- `dispatcher /health` stays 200 while media jobs run (search no longer competes for its threadpool)

## Fail events

- Empty fake results when a backend is down
- No `backend` field logged
- Skill calling `dispatcher:8090/v1/search`
