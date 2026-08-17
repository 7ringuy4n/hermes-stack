# monitor

## System architecture

| | |
|--|--|
| **Sits beside** | All stack services (scrape / log ship) |
| **Owns** | Grafana, Prometheus, Loki/Alloy, alert-watch |
| **Does not own** | Chat path — Low/Medium run without monitor |

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

High only (`ENABLE_GRAFANA` / Loki / Prometheus / Alloy).

## Sub-packages (from lab copy)

| Package | Function |
|---|---|
| `grafana/` | Dashboards |
| `alert-watch/` | Health / alert watcher |
| `stack-exporter/` / `nine-exporter/` | Exporters |

## How it works

```text
Services expose /health and metrics
    → Prometheus scrapes
    → Loki receives logs (via Alloy/agents)
    → Grafana dashboards on 127.0.0.1
```

Do not require monitor to run Low chat.

## Related

- [docs/00-profiles.md](../../docs/00-profiles.md)
