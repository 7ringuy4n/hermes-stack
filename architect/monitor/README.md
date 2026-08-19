# monitor

## System architecture

| | |
|--|--|
| **Sits beside** | All stack services (scrape / log ship) |
| **Owns** | Grafana, Prometheus, Loki/Alloy, paired exporters, alert-watch |
| **Does not own** | Chat path — Low/Medium/High run without monitor |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Stack services</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>Prometheus · Loki · Grafana</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">alert-watch</td>
  </tr>
</table>

## Purpose

Observability for High: metrics, logs, dashboards. Access via **localhost or SSH tunnel** (or edge when Traefik/OpenVPN is enabled).

## Profile

High optional. Flags are independent combos:

| Flag | Starts together |
|------|-----------------|
| `ENABLE_GRAFANA=1` | Grafana + **Prometheus** + `nine-exporter` + `node-exporter` (Hardware panels) + `stack-exporter` |
| `ENABLE_PROMETHEUS=1` | Prometheus + the same exporters (no Grafana UI) |
| `ENABLE_LOKI=1` or `ENABLE_ALLOY=1` | **Loki + Alloy** |
| `ENABLE_OMNIROUTER=1` + Prometheus/Grafana | OmniRouter + **`omni-exporter`** |

Extra usage: Grafana+Prometheus **~1.5 GiB · ~10 GB · ~0.5 vCPU**, Loki+Alloy **~1.5 GiB · ~20 GB · ~0.5 vCPU**, all optional features **~5 GiB RAM · ~40 GB disk · ~2 vCPU**. See [docs/HARDWARE.md](../../docs/HARDWARE.md).

## Sub-packages

| Package | Function | Pairs with |
|---|---|---|
| `grafana/` | Dashboards | Prometheus (metrics/Hardware) and/or Loki (logs) |
| `alert-watch/` | Health / alert watcher | Notify (`ENABLE_NOTIFY=1`). Scrapes **node-exporter only when Grafana/Prometheus is on**. Optional health targets (AV, Zalo, Omni, OCR, OpenBao) are skipped when their `ENABLE_*` is off. DNS failures for disabled hosts are not alerts. |
| `nine-exporter/` | 9Router usage metrics | 9Router + Prometheus |
| `omni-exporter/` (same image as nine-exporter) | OmniRoute usage metrics | OmniRouter + Prometheus |
| `stack-exporter/` | `assistant_service_up` + Redis/Qdrant | Grafana stack health + Prometheus |
| `node-exporter` (image `prom/node-exporter`) | Host CPU/RAM | Grafana **Hardware** panels + Prometheus |

## How it works

```text
Paired exporters expose /metrics
    → Prometheus scrapes (only jobs whose exporters are up)
    → Loki receives logs (via Alloy)
    → Grafana dashboards on 127.0.0.1:23000
```

Do not require monitor to run Low chat.

## Tests

When Grafana (or Prometheus-only) is on, run case **20** (`test/scripts/grafana_integration_lab.py`, SSH) and local `grafana_pairing_unit.py`. 9Router is always-on: stack-exporter probes it over **TCP** (UI `/health` is 404). OmniRouter scrape is required only if `ENABLE_OMNIROUTER=1`.

## Related

- [docs/00-profiles.md](../../docs/00-profiles.md)
- [docs/HARDWARE.md](../../docs/HARDWARE.md)
