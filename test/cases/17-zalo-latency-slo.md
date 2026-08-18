# Case: Zalo simple-message latency SLO

Measure end-to-end latency for **short text** on Zalo (High).

## Goal

Detect slow paths. A **simple text** reply on the host (no WAN hop) must be **as fast as possible**. **> 5s** is slow unless proven network latency.

## Preconditions

- High, Zalo on, Hermes×2, bridge `sseClients=1`
- No image/media in this case

## Steps

1. Run `python test/scripts/zalo_latency_lab.py` (batch size 5, separate process)
2. Record per-message: start, end, latency ms, HTTP/status
3. Compute min / p50 / p95 / max
4. Repeat with UTF-8 Vietnamese short ping

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

- [ ] model-router / 9router health and combo warm
- [ ] Valkey session lock contention
- [ ] OmniRouter vs 9router path for general chat
- [ ] stack-watch not restarting Hermes mid-turn
- [ ] Zalo inflight cap (`HERMES_MAX_ANSWERING`)
