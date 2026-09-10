# Case: default Router Worker and OmniRoute connectivity

Check **component defaults** vs **live** `.env`, then prove Hermes can reach the routers that should be on.

## Defaults (SoT: `architect/backup-restore/lib/workers.sh`)

| Item | Default |
|------|---------|
| OmniRoute | **on by default** (`ENABLE_OMNIROUTER=active`) |
| Router Worker (`ENABLE_ROUTER_WORKER`) | **active** (container and DNS `router-worker`) |
| Schedule / media / security / notify / message / monitor | **inactive** |
| `ENABLE_GRAFANA` / Prometheus / Loki | **inactive** |
| Hermes `OPENAI_BASE_URL` | `http://router-worker:8096/v1` |

Lab helper `test/scripts/deploy_high.py` is legacy; use `WORKER_*` / `ENABLE_*` on the host `.env`. Set `ENABLE_OMNIROUTER=0` only when a lab must force a non-default path, and enable `ENABLE_OMNIROUTER=1` if coding / fallback depends on it.

## Connectivity

```text
Hermes → INPUT Secret Probe → task_hint (explicit or default normal)
       → POST /v1/classify when schedule/multi-task intercept needs structure
       → router-worker → OmniRoute named combo
```

| Flag live | Must be true |
|-----------|----------------|
| `ENABLE_ROUTER_WORKER=active` (default) | `router-worker` `/health` 200; Hermes can open `http://router-worker:8096/health` |
| `ENABLE_OMNIROUTER=active` | `omni-router` GET `/` 2xx/3xx; router-worker config points at it |
| `ENABLE_OMNIROUTER=inactive` | `omni-router` may be absent; endpoint-capable, explicitly configured Router Worker fallbacks must be tested |

## Steps

**Unit (no VPS):** `python test/scripts/defaults_profile_unit.py`

**Lab (SSH, separate process):** `python test/scripts/defaults_routers_lab.py`

1. Dump live flags (no secrets).
2. Compare to the table above — **RECORD** mismatches (lab overrides are OK if labelled).
3. Hermes→router-worker probe.
4. OmniRoute is present **iff** the compatibility flag `ENABLE_OMNIROUTER` is active.
5. Optional: one short `router-worker` chat ping; if latency **> 5s** on localhost, mark **SLOW** (case 17).

## Pass criteria

- Unit: worker defaults match the table
- Router Worker health identifies `service=router-worker` under its canonical container and DNS name
- no retired task-aware proxy container, environment key, or default URL remains after upgrade cleanup
- OmniRoute container matches the live compatibility flag
- Simple chat does not crash when the chosen router path is disabled or switched intentionally

## Fail events

- Hermes cannot reach router-worker
- `ENABLE_OMNIROUTER=0` but docs/tests still assume it is always on
- `ENABLE_OMNIROUTER=0` but the alternate route is not enabled / not working
- `ENABLE_OMNIROUTER=1` but Grafana `omnirouter_scrape_success==0` (case 20)
