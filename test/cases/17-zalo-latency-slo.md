# Case: Zalo simple-message latency SLO

Measure end-to-end latency for **short text** on Zalo.

## Goal

Detect slow paths on the **Zalo / Hermes / queue** side. A **simple text** reply on the host (no WAN hop) should be **as fast as possible**. **> 5s** is slow unless the delay is **free-model switch, provider failover, or quota/rate-limit**.

## Preconditions

- Message worker on, Hermes running, bridge `sseClients=1`
- No image/media in this case

## Steps

1. Run `python test/scripts/zalo_user_latency.py` (Zalo Bridge `POST /inject-event` as the allowlisted user named `ZALO_TEST_USER_NAME`, default display name `Tn`; text `ZALO_LATENCY_TEXT` default `hi`). Do **not** bypass the bridge with Traefik `/v1/chat/completions`.
2. Record inject → inbound log → `Zalo: send ok` ms. Bridge `sseClients` must stay `1`.
3. If send is **> 5s**, inspect Hermes / model-router / OmniRoute logs for quota (`429`, `quota`, `rate limit`) or provider fallback (`switch`, `failover`, `no healthy`, `trying next`). Those are **not** service-hang failures, but remain latency evidence.
4. Optional extra: `python test/scripts/zalo_latency_lab.py` for Traefik-only comparison (not the Zalo path).

## Pass criteria

| Metric | Target | Record |
|--------|--------|--------|
| each sample | ≤ **5s** | actual |
| p50 | ≤ **5s** | actual |
| p95 | ≤ **5s** | actual |
| max | ≤ **5s** | actual |

If any sample **> 5s** and logs show **quota / 429 / free-model switch**: **PASS with note** (not a Zalo-path regression).

If any sample **> 5s** without those causes: **FAIL** (Valkey lock, Hermes queue, Zalo SSE, stack-watch restart).

## Fail events

- Any message > 120s timeout (unless quota exhausted with no remaining provider)
- Hermes restart during burst
- User sees stack trace or job id

## Improvement checklist (when FAIL)

- [ ] Classify hop (`classify.json` timeout, `MODEL_ROUTER_CLASSIFY_TIMEOUT_S`)
- [ ] model-router / OmniRoute health (quota vs real hang)
- [ ] Valkey session lock contention
- [ ] stack-watch not restarting Hermes mid-turn
- [ ] Zalo inflight cap (`HERMES_MAX_ANSWERING`)
