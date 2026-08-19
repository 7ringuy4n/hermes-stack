# Case: default flags — 9Router / OmniRouter connected

Check **profile defaults** vs **live** `.env`, then prove Hermes can reach the routers that should be on.

## Defaults (SoT: `architect/backup-restore/lib/profile.sh`)

| Item | Low | Medium | High |
|------|-----|--------|------|
| 9Router | **always on** (no `ENABLE_9ROUTER`) | same | same |
| `ENABLE_MODEL_ROUTER` | **1** | **1** | **1** |
| `ENABLE_OMNIROUTER` | **1** (Low/Medium) | **1** | **0** (opt-in) |
| `ENABLE_GRAFANA` / Prometheus / Loki | **0** | **0** | **0** (opt-in) |
| Hermes `OPENAI_BASE_URL` | `http://model-router:8096/v1` when model-router on | same | same |

Lab helper `test/scripts/deploy_high.py` follows the same defaults (**OmniRouter=0**, **Grafana/Prometheus/Loki=0**). Set `ENABLE_OMNIROUTER=1` and/or `ENABLE_GRAFANA=1` on the environment when a lab needs them. Dedicated scripts (`switch_omnirouter_image.py`, `deploy_omni_grafana.py`) still turn Omni/Grafana on for those jobs.

## Connectivity

```text
Hermes → INPUT Secret Probe → task_hint (explicit or default normal)
       → POST /v1/classify when schedule/multi-task intercept needs structure
       → model-router → 9router (coding) / OmniRouter (general, if enabled)
```

| Flag live | Must be true |
|-----------|----------------|
| always | `9router` container running; Hermes replica can open `http://9router:20128/` |
| `ENABLE_MODEL_ROUTER=1` (default) | `model-router` `/health` 200; Hermes can open `http://model-router:8096/health` |
| `ENABLE_OMNIROUTER=1` | `omni-router` GET `/` 2xx/3xx; model-router config points at it |
| `ENABLE_OMNIROUTER=0` (default) | `omni-router` **absent**; simple chat still works via 9Router |

## Steps

**Unit (no VPS):** `python test/scripts/defaults_profile_unit.py`

**Lab (SSH, separate process):** `python test/scripts/defaults_routers_lab.py`

1. Dump live flags (no secrets).
2. Compare to the table above — **RECORD** mismatches (lab overrides are OK if labelled).
3. Hermes→9router and Hermes→model-router probes.
4. OmniRouter present **iff** flag is 1.
5. Optional: one short `model-router` chat ping; if latency **> 5s** on localhost, mark **SLOW** (case 17).

## Pass criteria

- Unit: profile.sh strings match the table
- 9Router always reachable from Hermes
- Model-router healthy when default 1
- OmniRouter container matches the live flag
- Simple chat does not crash if OmniRouter is off

## Fail events

- Hermes cannot reach 9Router
- `ENABLE_OMNIROUTER=0` but OmniRouter still required for general chat (no 9Router fallback)
- `ENABLE_OMNIROUTER=1` but Grafana `omnirouter_scrape_success==0` (case 20)
