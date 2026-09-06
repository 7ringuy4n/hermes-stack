# Case: Grafana component integration

When **Grafana is enabled**, every **deployed** scrape target must show up in Prometheus (and therefore Grafana). Skip the whole case if `ENABLE_GRAFANA=0`.

## Pairing (SoT)

| Deployed component | Metric / job | Starts with |
|--------------------|--------------|-------------|
| Stack HTTP/TCP health | `assistant_service_up{service=…}` via `stack-exporter` | Grafana or Prometheus |
| OmniRoute (`ENABLE_OMNIROUTER=active`) | `assistant_service_up{service="omni-router"}` + `omnirouter_scrape_success` | OmniRoute **and** Grafana/Prometheus |
| Host CPU/RAM | `node_cpu_seconds_total` / `node_memory_MemAvailable_bytes` | Grafana/Prometheus → `node-exporter` |
| Grafana UI | `GET /api/health` → `database=ok` | `ENABLE_GRAFANA=1` |

Optional services that are **off** must not be required `=1` (example: `av-gateway` when `ENABLE_ANTIVIRUS=0`). Dashboard query already excludes `av-gateway|clamav|notify|alert-watch`.

## Steps (SSH lab — separate process)

1. Skip if `ENABLE_GRAFANA!=1`.
2. Run `python test/scripts/grafana_integration_lab.py`
3. Record Prometheus `activeTargets` job + health.
4. Record `assistant_service_up` for each expected service (from live flags).
5. Record `omnirouter_scrape_success` when OmniRoute is active.
6. If OmniRoute is on: `omnirouter_scrape_success==1`. If off: omni-exporter job may be absent — **PASS**.
7. Grafana `/api/health` database ok.

## Pass criteria

- Grafana health ok
- Prometheus jobs that should run are `up`
- Expected `assistant_service_up==1` (including **omni-router** TCP)
- OmniRoute scrape success **only if** that flag is active

## Fail events

- Grafana on but Prometheus target `stack-exporter` down
- Deployed OmniRoute with `assistant_service_up{service="omni-router"}==0` (wrong `/health` path)
- OmniRoute container up but TCP probe 0
- Dashboard Hardware panels empty because `node-exporter` not paired

## Local unit (no VPS)

`python test/scripts/grafana_pairing_unit.py` — compose `HEALTH_TARGETS` includes `omni-router`; Prometheus scrape jobs list OmniRoute, node, and stack exporters.
