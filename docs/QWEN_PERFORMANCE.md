# Qwen performance (lab)

Operator-facing snapshot of **current Qwen via OmniRouter combos** on the lab stack.
Do not put hostnames, accounts, or secrets here.

Companion: [`CHANGELOG.md`](./CHANGELOG.md), [`../scripts/HISTORY.md`](../scripts/HISTORY.md).

## Active combos (after slim)

| Combo | Members | Notes |
|-------|---------|--------|
| `hermes` | ≤2 Qwen chat models (lab: Qwen2.5-72B + 7B Instruct via provider RR) | Round-robin |
| `classifier` | 1 Qwen chat model | Intent / multi-request split |
| `qwen-fast` | Tiny ~1.5B/1.7B when catalog has them | Empty if none in catalog |

Non-Qwen LLM providers are deactivated when `OMNIROUTER_QWEN_ONLY_PROVIDERS=1`.

## Latency (lab, 2026-08-22)

Measured with Tn Zalo bridge inject + model-router probes.

| Path | Result |
|------|--------|
| Greeting inject → send ok | ~7.5–22 s E2E; Hermes `response ready` ~1.8–10 s |
| Short math inject | ~10–11 s E2E; `response ready` ~3 s |
| Model-router short chat | ~0.5–1.4 s |
| Model-router math `17×19` | ~0.7 s; answer **323** |

## Hardware headroom (same window)

| Resource | Observed |
|----------|----------|
| Host RAM | ~16 GB total; ~6.3 GB used; ~9.6 GB free |
| Disk `/` | ~25% used; ~149 GB free |
| load1 | 0.45–1.19 |
| Hermes RSS | ~313 MiB |
| Omni RSS | ~844 MiB |
| Container CPU (Hermes/Omni) | idle ~0–1%; spikes to ~100%+ on turns |

Conclusion: host has headroom for larger context; keep **7B for fast turns** and **72B for harder turns**. Dedicated `qwen-fast` needs a tiny Qwen id in the Omni catalog (or a local small provider).

## Weather / web-search failure mode (2026-08-22)

Symptom: `tìm thông tin thời tiết hồ chí minh hiện tại` took long / no useful reply.

Root cause (stacked):

1. Lab `router-worker` image was **stale** — `/app/websearch.py` lacked `GET /v1/searxng-compat/search` while Hermes `SEARXNG_URL` pointed at that shim → **404**.
2. OpenRouter intermittent **402/502/503** during the same window (credits / upstream).
3. Queue turn budget default **150 s** is tight when search cascades + LLM retries.

Mitigations:

- Rebuild/recreate `router-worker` from current `architect/models/model-router`.
- Keep `WEB_BACKENDS=omni` and Hermes `SEARXNG_URL=…/v1/searxng-compat`.
- Raise `ZALO_QUEUE_TURN_TIMEOUT_S` default to **300** and `WEB_SEARCH_PROVIDER_TIMEOUT_S` to **30**.
- Prefer non-thinking Qwen2.5; slim combos; disable Omni credential health spam.

## Tests

| Script | Purpose |
|--------|---------|
| `test/scripts/zalo_tn_greeting_inject.py` | Tn greeting |
| `test/scripts/zalo_tn_qwen_perf.py` | Latency + HW samples |
| `test/scripts/zalo_tn_weather_mixed_schedule.py` | Weather + mixed ≥3 + schedule multi-task |

Always inject as allowlisted user **Tn** via bridge `/inject-event` (id from host allowlist file — never commit).
