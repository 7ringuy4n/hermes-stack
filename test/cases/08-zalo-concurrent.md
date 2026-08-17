# Case: Zalo concurrent requests

Simulate many Zalo-originated chat turns at once (not browser dashboard).

## Goal

Verify Hermes × N + single Zalo SSE owner can absorb a burst of inbound text
without crash-loop, SSE double-attach, or gateway 429 storms (use authenticated
gateway when probing HTTP paths).

## Preconditions

- `ENABLE_ZALO=1`, bridge healthy, `loggedIn=true`, `sseClients=1`
- High profile preferred (Hermes×2)
- Do **not** open a second SSE client

## Steps

1. Confirm bridge `/health`: `loggedIn=true`, `sseClients=1`
2. Fire **N parallel** text turns via the Zalo plugin/Hermes inbound path
   (preferred: `zalo-api` chat helper or Hermes session API with Zalo thread ids —
   not a second bridge login)
3. Record per-request: start, end, HTTP/app status, latency
4. Ramp N = 4 → 8 → 16 → 24 until first failure (timeout / 5xx / drop)
5. After burst: re-check `sseClients=1`, Hermes replicas healthy, no crash loop
6. Optional: one media attachment in parallel with text (if Medium+)

## Pass criteria

- Last all-success N recorded; first-fail N recorded (or “no fail ≤24”)
- SSE owner remains exactly one
- No Hermes restart storm during the burst
- User-facing errors (if any) are short alerts, not stack traces

## Fixtures

- Run A: short ASCII pings (`zalo-c-a-{i}`)
- Run B: mixed UTF-8 / Vietnamese short lines (`zalo-c-b-{i}`)
