# Case: Zalo simple-message latency SLO

Measure end-to-end latency for **short text** on Zalo (High).

## Goal

Detect slow paths. A **simple text** reply on the host (no WAN hop) must be **as fast as possible**. **> 5s** is slow unless proven network latency.

## Preconditions

- High, Zalo on, Hermes×2, bridge `sseClients=1`
- No image/media in this case

## Steps

1. Run `python test/scripts/zalo_user_latency.py` (Zalo Bridge `POST /inject-event` as the allowlisted user named `ZALO_TEST_USER_NAME`, default display name `Tn`; text `ZALO_LATENCY_TEXT` default `hi`). Do **not** bypass the bridge with Traefik `/v1/chat/completions`.
2. Record inject → inbound log → `Zalo: send ok` ms. Bridge `sseClients` must stay `1`.
3. Optional extra: `python test/scripts/zalo_latency_lab.py` for Traefik-only comparison (not the Zalo path).

## Pass criteria

| Metric | Target | Record |
|--------|--------|--------|
| each sample | ≤ **5s** | actual |
| p50 | ≤ **5s** | actual |
| p95 | ≤ **5s** | actual |
| max | ≤ **5s** | actual |

If any sample **> 5s** (localhost Traefik, so not user WAN): **FAIL** and open a perf ticket (model-router, 9router cold start, Valkey lock, Hermes queue, OmniRouter vs 9router).

Lab 2026-08-18: p50 4.1s / p95 9.2s — **p95 misses the 5s SLO**; treat as improvement work, not a silent pass.

## Fail events

- Any message > 120s timeout
- Hermes restart during burst
- User sees stack trace or job id

## Improvement checklist (when FAIL)

- [ ] Classify hop (`classify.json` timeout/max_tokens, `MODEL_ROUTER_CLASSIFY_TIMEOUT_S`)
- [ ] model-router / 9router health and combo warm
- [ ] Valkey session lock contention
- [ ] OmniRouter vs 9router path for general chat
- [ ] stack-watch not restarting Hermes mid-turn
- [ ] Zalo inflight cap (`HERMES_MAX_ANSWERING`)
