# Case: default router flags — OmniRoute through compatibility settings

Check **component defaults** vs **live** `.env`, then prove Hermes can reach the routers that should be on.

## Defaults (SoT: `architect/backup-restore/lib/workers.sh`)

| Item | Default |
|------|---------|
| OmniRoute | **on by default** through the compatibility flag (`ENABLE_OMNIROUTER=active`) |
| Model Router (`ENABLE_MODEL_ROUTER`) | **1** (container `model-router`, DNS alias `model-router`) |
| `ENABLE_OMNIROUTER` | **1** |
| Schedule / media / security / notify / message / monitor | **0** |
| `ENABLE_GRAFANA` / Prometheus / Loki | **0** |
| Hermes `OPENAI_BASE_URL` | `http://model-router:8096/v1` |

Lab helper `test/scripts/deploy_high.py` is legacy; use `WORKER_*` / `ENABLE_*` on the host `.env`. Set `ENABLE_OMNIROUTER=0` only when a lab must force a non-default path, and enable `ENABLE_OMNIROUTER=1` if coding / fallback depends on it.

## Connectivity

```text
Hermes → INPUT Secret Probe → task_hint (explicit or default normal)
       → POST /v1/classify when schedule/multi-task intercept needs structure
       → model-router → OmniRoute named combo
```

| Flag live | Must be true |
|-----------|----------------|
| `ENABLE_MODEL_ROUTER=1` (default) | `model-router` `/health` 200; Hermes can open `http://model-router:8096/health` |
| `ENABLE_OMNIROUTER=1` | `omni-router` GET `/` 2xx/3xx; model-router config points at it |
| `ENABLE_OMNIROUTER=1` | `omni-router` container running; Hermes replica can open `http://omni-router:20129/` |
| `ENABLE_OMNIROUTER=0` | `omni-router` **absent**; only valid if the intended alternate router path is enabled and tested |

## Steps

**Unit (no VPS):** `python test/scripts/defaults_profile_unit.py`

**Lab (SSH, separate process):** `python test/scripts/defaults_routers_lab.py`

1. Dump live flags (no secrets).
2. Compare to the table above — **RECORD** mismatches (lab overrides are OK if labelled).
3. Hermes→model-router probe.
4. OmniRoute is present **iff** the compatibility flag `ENABLE_OMNIROUTER` is active.
5. Optional: one short `model-router` chat ping; if latency **> 5s** on localhost, mark **SLOW** (case 17).

## Pass criteria

- Unit: worker defaults match the table
- Model-router healthy when default 1
- OmniRoute container matches the live compatibility flag
- Simple chat does not crash when the chosen router path is disabled or switched intentionally

## Fail events

- Hermes cannot reach model-router
- `ENABLE_OMNIROUTER=0` but docs/tests still assume it is always on
- `ENABLE_OMNIROUTER=0` but the alternate route is not enabled / not working
- `ENABLE_OMNIROUTER=1` but Grafana `omnirouter_scrape_success==0` (case 20)
