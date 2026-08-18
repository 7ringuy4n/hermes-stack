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

## Lab script (preferred)

From repo root (separate process from other cases):

```bash
python test/scripts/zalo_concurrent.py
```

Uses `POST /v1/zalo/chat` on zalo-api with synthetic sender/thread ids (no second SSE
login). Report: `test/reports/run-zalo-concurrent/`.

Optional env: `ZALO_CONCURRENT_MAX=24`.

## Steps

1. Confirm bridge `/health`: `loggedIn=true`, `sseClients=1`
2. Fire **N parallel** text turns via the Zalo plugin/Hermes inbound path
   (preferred: lab script above — not a second bridge login)
3. Record per-request: start, end, HTTP/app status, latency
4. Ramp N = 4 → 8 → 16 → 24 until first failure (timeout / 5xx / drop)
5. After burst: re-check `sseClients=1`, Hermes replicas healthy, no crash loop
6. **Required:** mixed burst with **text and media generation in the same window** (see `cases/09-zalo-concurrent-media.md` + `test/scripts/zalo_concurrent_media.py`). Record per-kind latency (p50/p95/max). Ramp until first fail.
7. **FIFO smoke (optional):** with Valkey queue on, send 4+ short pings in one thread within the rate window — expect rate-limit notice then **all** answers (case 23); cap default **3** waiting items per thread.

## Pass criteria

- Last all-success N recorded; first-fail N recorded (or “no fail ≤24”)
- SSE owner remains exactly one
- No Hermes restart storm during the burst
- User-facing errors (if any) are short alerts, not stack traces

## Fixtures

- Run A: short ASCII pings (`zalo-c-a-{i}`)
- Run B: mixed UTF-8 / Vietnamese short lines (`zalo-c-b-{i}`)
