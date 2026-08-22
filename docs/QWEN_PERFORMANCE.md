# Qwen performance & concurrency sizing

Operator-facing guide for **Qwen as an optional OmniRouter component** and
recommended Zalo/workflow parallelism by host size.

Do not put hostnames, accounts, or secrets here.

Companions: [`CHANGELOG.md`](./CHANGELOG.md), [`../scripts/HISTORY.md`](../scripts/HISTORY.md).

## Component switch

| Knob | Default | Meaning |
|------|---------|---------|
| `ENABLE_QWEN` | `0` | Qwen is inactive until the operator turns it on |
| `QWEN_API_KEY` / `ALIBABA_API_KEY` / `DASHSCOPE_API_KEY` | empty | Required when `ENABLE_QWEN=1` |
| `OMNIROUTER_COMBO_STRATEGY` | `round-robin` | Strategy for `hermes` / `classifier` |
| `hermes` / `classifier` members | **empty** | Filled only when Qwen is active + key yields chat models |
| `OMNIROUTER_QWEN_ONLY_PROVIDERS` | `1` | When Qwen is active, deactivate non-Qwen LLM providers (skipped if `ENABLE_QWEN=0`) |
| `OMNIROUTER_QWEN_FAST_COMBO` | `qwen-fast` | Optional tiny (~1.5B/1.7B) combo; empty if catalog has none |
| `ZALO_WORKFLOW_PARALLEL` | **8** | Default parallel workflow jobs per turn (targets 5–10 concurrent multi-request users) |

Activate on a host:

```text
ENABLE_QWEN=1
QWEN_API_KEY=<dashscope-or-alibaba-key>
bash run.sh add-components ENABLE_QWEN=1   # or edit .env then re-run first-setup-omnirouter
```

## Active combos (when Qwen on)

| Combo | Members | Notes |
|-------|---------|--------|
| `hermes` | ≤2 Qwen chat models (prefer Qwen2.5 instruct; avoid think-only Qwen3) | Round-robin |
| `classifier` | 1 Qwen chat model | Intent / multi-request split |
| `qwen-fast` | Tiny ~1.5B/1.7B when catalog has them | Empty if none |

When Qwen is **off**, first-setup still creates `hermes` + `classifier` as **empty** round-robin aliases (operator adds models in Omni Combos UI).

## Recommended `ZALO_WORKFLOW_PARALLEL` by host profile

These are **starting recommendations** for Omni cloud Qwen (not local GPU weights).
They assume Hermes + Router Worker + Valkey on the same host and ~5–10 concurrent
Zalo users with multi-request bubbles. Validate with
`test/scripts/zalo_tn_qwen_parallel_sizing.py` (Tn inject) before production.

| Profile (vCPU / RAM) | Recommended parallel | Concurrent users (guidance) | Notes |
|----------------------|----------------------|-----------------------------|--------|
| 1 / 1 GB | 2 | 1–2 | Too small for full stack; expect queue waits |
| 1 / 2 GB | 3 | 2–3 | Prefer `qwen-fast` / 7B only; slim combos |
| 2 / 2 GB | 4 | 3–5 | Minimum practical lab |
| 2 / 4 GB | 6 | 5–8 | Good for mixed text + light tools |
| 4 / 8 GB | **8** (product default) | 5–10 | Target for multi-request Zalo |
| 4 / 16 GB | 10 | 8–12 | Headroom for weather/search tools |
| 8 / 16 GB | 12 | 10–16 | Scale Hermes replicas if SSE/queue saturates |
| 8 / 32 GB | 16 | 12–20 | Watch Omni upstream rate limits |

Rule of thumb: `parallel ≈ min(vCPU * 2, RAM_GB, 16)` then clamp to the table.
Never raise parallel alone if Omni returns 402/503 — slim combos and fail over first.

## Latency snapshot (lab, 2026-08-22)

Measured with Tn Zalo bridge inject + model-router probes (prior lab host; not a sizing claim).

| Path | Result |
|------|--------|
| Greeting inject → send ok | ~7.5–22 s E2E; Hermes `response ready` ~1.8–10 s |
| Short math inject | ~10–11 s E2E; `response ready` ~3 s |
| Weather HCMC (after searxng-compat rebuild) | first send ~15 s |
| Mixed ≥3 requests | 4 sends; first ~10 s, last ~18 s |
| Schedule multi-task | send ~10 s; ack PASS |

## Tavily vs “SEARXNG” naming

| Knob | Meaning |
|------|---------|
| Hermes `SEARXNG_URL` | Router Worker **SearXNG-shaped shim** (`/v1/searxng-compat`) — not “prefer SearXNG engine” |
| `OMNIROUTER_SEARCH_PROVIDERS` | Forced cascade: **tavily → firecrawl → searxng** |
| Omni unforced `POST /v1/search` | Often labels `searxng-search` even when Tavily is healthy — do not treat as Hermes default |

## Tests

| Script | Purpose |
|--------|---------|
| `test/scripts/zalo_tn_greeting_inject.py` | Tn greeting |
| `test/scripts/zalo_tn_qwen_perf.py` | Latency + HW samples |
| `test/scripts/zalo_tn_qwen_parallel_sizing.py` | Recommend / probe parallel by profile |
| `test/scripts/zalo_tn_weather_mixed_schedule.py` | Weather + mixed ≥3 + schedule |
| `test/scripts/zalo_tn_history_regression.py` | HISTORY no-reply / PDF / schedule / SOUL gaps |
| `test/scripts/soul_deception_unit.py` | SOUL must not trip `deception_hide` |
| `test/scripts/qwen_parallel_recommend_unit.py` | Offline sizing table unit |

Always inject as allowlisted user **Tn** via bridge `/inject-event` (id from host allowlist file — never commit).
