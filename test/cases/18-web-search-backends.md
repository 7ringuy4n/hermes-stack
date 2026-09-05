# Case: web search combo (Model Router)

Verify `/v1/search` on **model-router** (`model-router:8096`) proxies to Omni combo **web-search**.

## Default path

When `OMNIROUTER_BASE_URL` and `OMNIROUTER_API_KEY` are set:

1. Model Router posts `{ combo: web-search, query, max_results }` to Omni `POST /v1/search`
2. Failover order and provider members are owned in Omni UI (not env `WEB_BACKENDS`)
3. Response `backend` reports combo name `web-search`

Missing Omni config → 503 controlled error.

## Steps (unit/local)

1. Run `python test/scripts/websearch_combo_unit.py`
2. Run `python test/scripts/web_search_backends_unit.py` (when model-router is up)
3. POST `/v1/search` with `{"query":"weather Ho Chi Minh","max_results":3}`
4. Record the `backend` and `combo` fields in the JSON response

## Steps (lab)

1. Case 04 weather query via Zalo → Hermes
2. Confirm Omni logs show combo `web-search` (member provider names may appear inside combo)
3. Confirm the media worker no longer serves search: `POST dispatcher:8090/v1/search` → 404

## Pass criteria

- Search returns `backend` = combo name (`web-search`)
- No Omni config: 503 + short message, no crash
- Hermes does not fabricate weather/fuel when search fails
- `dispatcher /health` stays 200 while media jobs run (search no longer competes for its threadpool)

## Fail events

- Empty fake results when Omni is down
- No `backend` field logged
- Skill calling `dispatcher:8090/v1/search`
- Direct Tavily/Firecrawl/SearXNG adapter chain bypassing Omni combo
