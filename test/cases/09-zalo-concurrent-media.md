# Case: Zalo concurrent text + media generation

Simulate a Zalo-originated burst where **text turns and image generation run at the same time**.
Watch delay (per-request latency, p50/p95/max), not only pass/fail.

This is not a second Zalo SSE client. Text goes through **Traefik** `:8080/v1/chat/completions`
with **`API_SERVER_KEY`** (Hermes chat auth). Media generation goes through dispatcher
`POST /v1/image` (the same path the Zalo adapter uses for outbound images).

Do **not** use Gateway `:8088` alone for the text half — Hermes expects `API_SERVER_KEY` on the
Traefik path; Gateway-only auth returned **503** in lab run-04.

## Goal

- Mixed load does not crash Hermes×2, drop Zalo SSE (`sseClients=1`), or storm Gateway 429s.
- Image gen delay is recorded separately from text delay.
- Ramp until the **first** fail (timeout / 5xx / drop / crash).

## Preconditions

- High, `ENABLE_ZALO=1`, bridge `loggedIn=true`, `sseClients=1`
- Image backends configured (Medium+/High `IMAGE_BACKENDS` non-empty)
- `API_SERVER_KEY` set (required for text burst on Traefik `:8080`)
- `GATEWAY_API_KEYS` optional (fallback only if `API_SERVER_KEY` empty)

## Steps

1. Record bridge health and Hermes replica count.
2. For N in 2 → 4 → 8 → 12 (half text, half image, interleaved):
   - Text: `POST` Traefik `:8080/v1/chat/completions` with `Authorization: Bearer $API_SERVER_KEY` (short ping, `max_tokens` small).
   - Image: `POST` dispatcher `/v1/image` with `refine=false` and a tiny prompt.
3. Per request record: kind, HTTP status, start, end, latency_ms.
4. After each burst: SSE still 1, Hermes still up, no crash loop.
5. Stop at first fail. Record last all-success N and first-fail N + failure mode.

## Pass criteria

- Last all-success N and first-fail N recorded (or “no fail ≤12”).
- Text and image latency tables present (p50 / p95 / max).
- SSE owner remains one; Hermes replicas healthy.
- Failures (if any) are short alerts, not stack traces.

## Fixtures

- Run A: ASCII pings + prompt `tiny red square test`
- Run B: Vietnamese short lines + prompt `ô vuông đỏ nhỏ`
