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
| Weather HCMC (after searxng-compat rebuild) | first send ~15 s; `response ready` ~7.6 s (136 chars); suite PASS |
| Mixed ≥3 requests (greet + math + Hà Nội weather) | 4 sends; first ~10 s, last ~18 s; 3× `response ready` (3.0s / 6.4s / 10.5s) |
| Schedule multi-task (3 items @ 23:55) | send ~10 s; ack PASS (no queue timeout) |

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

## Tavily vs “SEARXNG” naming (not the same as default engine)

| Knob | Meaning |
|------|---------|
| Hermes `SEARXNG_URL` / `HERMES_SEARXNG_URL` | Points at Router Worker **SearXNG-shaped shim** (`/v1/searxng-compat`). Hermes native `web_search` speaks that protocol; the shim still runs the Omni cascade. |
| Router `SEARXNG_URL=http://searxng:8080` | Direct local SearXNG container — used only as Omni’s **fallback** adapter base URL. |
| `OMNIROUTER_SEARCH_PROVIDERS` | Router Worker forced order when calling Omni: **tavily → firecrawl → searxng**. |
| Omni provider **priority** | Unforced Omni `POST /v1/search` (UI / smoke). Must be Tavily=1, Firecrawl=2, SearXNG=3. |

If Omni shows Tavily active but `provider=searxng-search` on unforced search, both connections likely share **priority=1** (tie → SearXNG). Re-run `scripts/main/first-setup-omnirouter.py` (enforce pass) or `test/scripts/apply_omni_tavily_priority.py`. Hermes weather via shim should still report `backend=omni:tavily-search` when the router cascade is healthy.

## Tests

| Script | Purpose |
|--------|---------|
| `test/scripts/zalo_tn_greeting_inject.py` | Tn greeting |
| `test/scripts/zalo_tn_qwen_perf.py` | Latency + HW samples |
| `test/scripts/zalo_tn_weather_mixed_schedule.py` | Weather + mixed ≥3 + schedule multi-task |

Always inject as allowlisted user **Tn** via bridge `/inject-event` (id from host allowlist file — never commit).
